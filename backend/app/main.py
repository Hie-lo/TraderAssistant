import os
import shutil
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from aiogram.exceptions import TelegramConflictError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.core.config import settings
from app.core.logger import logger, TelegramLogNotifier
from app.core.dynamic_config import DynamicConfig
from app.core.access_control import AccessControl
from app.database.session import engine, AsyncSessionLocal, ensure_schema_columns
from app.database.seed import seed_initial_settings
from app.models.base import Base
from app.services.market_service import MarketService
from app.services.alert_service import AlertService
from app.api.middlewares import GlobalErrorCatcherMiddleware
from app.api.v1.router import api_v1_router
from app.api.v1.trades import router as trades_router
from app.api.v1.admin import router as admin_router
from app.api.v1.payments import router as payments_router
from app.api.v1.market import connection_manager as market_connection_manager
from app.bot.loader import bot, dp
from app.bot.middlewares import BotAccessControlMiddleware
from app.bot.handlers import user_start, user_alerts, user_screener, admin_panel

# Ensure storage directories
os.makedirs(os.path.join(settings.STORAGE_DIR, "charts_auto"), exist_ok=True)
os.makedirs(os.path.join(settings.STORAGE_DIR, "charts_custom"), exist_ok=True)

scheduler = AsyncIOScheduler()
bot_polling_task = None


async def watchdog_task():
    """Periodic 2-minute server vitals healthcheck."""
    try:
        # Check DB
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))

        # Check Disk
        total, used, free = shutil.disk_usage(".")
        free_pct = (free / total) * 100
        if free_pct < 10.0:
            logger.critical(f"Server disk space critically low: {free_pct:.1f}% free!")
            await TelegramLogNotifier.notify_admin_channel(
                trace_id="DISK_WARN",
                section="WATCHDOG / STORAGE",
                exc=Exception("Low disk space"),
                extra_info=f"Free: {free // (2**30)} GB ({free_pct:.1f}%)"
            )
    except Exception as e:
        logger.error(f"Watchdog healthcheck alert: {e}")


async def periodic_alerts_check_task():
    """Runs every 30 seconds to evaluate smart price alerts."""
    try:
        async with AsyncSessionLocal() as session:
            await AlertService.check_all_active_alerts(session)
    except Exception as e:
        logger.warning(f"Error during periodic alerts check: {e}")


async def _run_bot():
    try:
        logger.info("Connecting to Telegram Bot API...")
        me = await bot.get_me()
        logger.info(f"✅ Telegram bot connected: @{me.username} (ID: {me.id})")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared previous webhooks. Starting Aiogram polling loop...")
        await dp.start_polling(bot, handle_signals=False)
    except TelegramConflictError as e:
        logger.critical(
            f"❌ Telegram bot polling conflict (another instance is polling with the same token): {e}"
        )
    except asyncio.CancelledError:
        logger.info("Telegram bot polling task cancelled.")
        raise
    except Exception as e:
        logger.critical(f"❌ Telegram bot polling failed to start or stopped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: orchestrates DB schema, RAM caches, scheduler, and background bot polling."""
    global bot_polling_task
    logger.info("Initializing Trading Assistant backend...")

    # 1. Create DB tables with retry loop in case PostgreSQL DNS/startup lags behind backend
    max_db_attempts = 5
    retry_delay_sec = 3
    for attempt in range(1, max_db_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await ensure_schema_columns(conn)
            logger.info("Database schema verified.")
            break
        except Exception as e:
            if attempt == max_db_attempts:
                logger.error(f"Database initialization failed after {max_db_attempts} attempts: {e}")
                raise
            logger.warning(
                f"Database not ready (attempt {attempt}/{max_db_attempts}): {e}. Retrying in {retry_delay_sec}s..."
            )
            await asyncio.sleep(retry_delay_sec)

    # 2. Seed default dynamic configuration
    try:
        async with AsyncSessionLocal() as session:
            await seed_initial_settings(session)
            await DynamicConfig.load_all(session)
            await AccessControl.load_restricted_users(session)
    except Exception as e:
        logger.error(f"Failed to seed / load dynamic configs: {e}")

    # 3. Setup and start APScheduler
    scheduler.add_job(periodic_alerts_check_task, "interval", seconds=30, id="price_alerts")
    scheduler.add_job(watchdog_task, "interval", minutes=2, id="system_watchdog")
    scheduler.start()
    logger.info("APScheduler background jobs started.")

    # 4. Setup Bot Handlers & Middlewares
    dp.message.outer_middleware(BotAccessControlMiddleware())
    dp.callback_query.outer_middleware(BotAccessControlMiddleware())

    dp.include_router(user_start.router)
    dp.include_router(user_alerts.router)
    dp.include_router(user_screener.router)
    dp.include_router(admin_panel.router)

    # 5. Start Bot Polling in background task if valid token
    if settings.BOT_TOKEN and "Placeholder" not in settings.BOT_TOKEN:
        bot_polling_task = asyncio.create_task(_run_bot())
    else:
        logger.warning(f"BOT_TOKEN is not configured or placeholder ('{settings.BOT_TOKEN[:12]}...'). Bot polling skipped.")

    yield

    # Shutdown sequence
    logger.info("Initiating shutdown sequence...")
    if scheduler.running:
        scheduler.shutdown(wait=False)

    await market_connection_manager.shutdown()

    if bot_polling_task and not bot_polling_task.done():
        bot_polling_task.cancel()
        try:
            await bot_polling_task
        except asyncio.CancelledError:
            pass

    if settings.BOT_TOKEN and "Placeholder" not in settings.BOT_TOKEN:
        try:
            await bot.session.close()
        except Exception:
            pass

    await MarketService.close()
    await engine.dispose()
    logger.info("Shutdown completed cleanly.")


app = FastAPI(
    title="Trading Assistant & Risk Mini-App API",
    version="1.0.0",
    description="High-performance backend for Telegram Risk Calculator & Journal Mini-App",
    lifespan=lifespan
)

# Global Error Handler Middleware
app.add_middleware(GlobalErrorCatcherMiddleware)

# CORS Middleware (permitting all origin headers for Telegram WebApp)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory for candlestick charts & uploaded images
app.mount("/static", StaticFiles(directory=settings.STORAGE_DIR), name="static")

# Mount API v1 router + /api route aliases for direct /api/admin/* and /api/trades/* access
app.include_router(api_v1_router)
app.include_router(trades_router, prefix="/api", include_in_schema=False)
app.include_router(admin_router, prefix="/api", include_in_schema=False)
app.include_router(payments_router, prefix="/api", include_in_schema=False)


@app.get("/health", tags=["Health"])
async def health_check():
    """Healthcheck endpoint for Docker / orchestration."""
    return {
        "status": "healthy",
        "maintenance_mode": DynamicConfig.get("maintenance_mode", False),
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
