import asyncio
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user, check_heavy_limit, require_admin
from app.core.security import AuthenticatedUser
from app.core.dynamic_config import DynamicConfig
from app.database.session import AsyncSessionLocal
from app.models.trade import Trade
from app.repositories.trade_repo import TradeRepository
from app.repositories.user_repo import UserRepository
from app.schemas.trade_schema import TradeCreateSchema, TradeUpdateSchema, TradeResponseSchema
from app.schemas.common import ApiResponse
from app.services.trade_service import TradeService
from app.services.chart_service import ChartService
from app.services.channel_service import ChannelService
from app.services.market_service import MarketService
from app.services.risk_guard_service import RiskGuardService
from app.core.exceptions import AppException, NotFoundError, BusinessValidationError
from app.core.logger import logger

router = APIRouter(prefix="/trades", tags=["Trades"])


async def generate_and_attach_chart_task(
    trade_id: str,
    symbol: str,
    timeframe: str,
    entry: float,
    sl: Optional[float],
    tp: Optional[float]
):
    """
    Background worker that runs chart rendering without delaying the HTTP response.
    Zero-Defect Rule: Opens an independent AsyncSessionLocal session for the background task.
    """
    try:
        df = await MarketService.fetch_ohlcv_dataframe(symbol=symbol, timeframe=timeframe, limit=80)
        chart_url = await ChartService.generate_trade_chart(
            trade_id=trade_id,
            symbol=symbol,
            timeframe=timeframe,
            entry=entry,
            sl=sl,
            tp=tp,
            df=df
        )

        async with AsyncSessionLocal() as bg_session:
            res = await bg_session.execute(select(Trade).where(Trade.id == trade_id))
            trade = res.scalar_one_or_none()
            if trade and not trade.is_custom_chart:
                trade.chart_image_url = chart_url
                trade.has_chart_snapshot = True
                await bg_session.commit()
                logger.info(f"Attached chart {chart_url} to trade {trade_id}")
    except Exception as e:
        logger.warning(f"Background chart generation failed for trade {trade_id}: {e}")


@router.post("", response_model=TradeResponseSchema, status_code=201)
async def create_new_trade(
    trade_in: TradeCreateSchema,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new trade journal entry after checking Freemium/VIP limits."""
    # Check Freemium / VIP trade limit (DB user.role is single source of truth)
    db_user = await UserRepository(db).get_by_id(current_user.id)
    effective_role = db_user.role if db_user else current_user.role
    if effective_role == "USER":
        free_max_trades = int(DynamicConfig.get("free_max_trades", 15))
        total_trades = await TradeRepository(db).count_by_user(current_user.id)
        if total_trades >= free_max_trades:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"سقف مجاز ثبت معامله برای کاربران رایگان ({free_max_trades} معامله) به پایان رسیده است. "
                    f"برای ثبت نامحد معاملات، حساب خود را به VIP ارتقا دهید."
                )
            )

    trade, _ = await TradeService.create_trade(db, current_user.id, trade_in)

    # Schedule background chart generation
    background_tasks.add_task(
        generate_and_attach_chart_task,
        trade_id=str(trade.id),
        symbol=trade.symbol,
        timeframe=trade.chart_timeframe,
        entry=float(trade.entry_price),
        sl=float(trade.stop_loss) if trade.stop_loss else None,
        tp=float(trade.take_profit) if trade.take_profit else None
    )

    return TradeService.trade_to_response(trade)


@router.patch("/{trade_id}", response_model=TradeResponseSchema)
@router.put("/{trade_id}", response_model=TradeResponseSchema)
async def update_trade_dirty_state(
    trade_id: str,
    patch_in: TradeUpdateSchema,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Persists dirty state modifications and auto-edits live Telegram channel post if published."""
    trade, needs_sl_check = await TradeService.update_trade_dirty_state(
        session=db,
        user_id=current_user.id,
        trade_id=trade_id,
        patch_data=patch_in
    )

    # Auto-edit live Telegram channel caption if this trade was already published
    if trade.telegram_message_id:
        await ChannelService.sync_published_trade_caption(trade)

    # If status transitioned to SL, verify weekly drawdown
    if needs_sl_check:
        asyncio.create_task(RiskGuardService.check_weekly_drawdown(db, current_user.id))

    return TradeService.trade_to_response(trade)


@router.post("/{trade_id}/publish", response_model=TradeResponseSchema)
async def publish_trade_to_channel(
    trade_id: str,
    admin_user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin-only endpoint to publish a trade with chart snapshot & Jinja2 caption to Telegram channel."""
    try:
        res = await db.execute(select(Trade).where(Trade.id == str(trade_id)))
        trade = res.scalar_one_or_none()
        if not trade:
            logger.error(f"Publish aborted: Trade id='{trade_id}' not found in database (admin={admin_user.id}).")
            raise NotFoundError("معامله مورد نظر در پایگاه داده یافت نشد.")

        published_trade = await ChannelService.publish_trade(db, trade)
        return TradeService.trade_to_response(published_trade)
    except NotFoundError:
        raise
    except AppException as exc:
        logger.error(f"Publish failed for trade id='{trade_id}': {exc.message}")
        raise
    except Exception as exc:
        logger.error(f"Unexpected error publishing trade id='{trade_id}': {exc}")
        raise AppException(f"خطا در انتشار معامله: {exc}", status_code=500)


@router.post("/{trade_id}/chart-upload")
async def upload_custom_chart(
    trade_id: str,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(check_heavy_limit),
    db: AsyncSession = Depends(get_db)
):
    """Securely uploads, sanitizes, and attaches a custom user chart image to the trade."""
    res = await db.execute(select(Trade).where(Trade.id == trade_id, Trade.user_id == current_user.id))
    trade = res.scalar_one_or_none()
    if not trade:
        raise NotFoundError("معامله مورد نظر یافت نشد.")

    file_bytes = await file.read()
    if not file_bytes:
        raise BusinessValidationError("فایل ارسالی خالی است.")

    new_chart_url = await ChartService.process_custom_chart_upload(
        file_bytes=file_bytes,
        previous_image_url=trade.chart_image_url if trade.is_custom_chart else None
    )

    trade.chart_image_url = new_chart_url
    trade.is_custom_chart = True
    trade.has_chart_snapshot = True
    await db.commit()

    return {"success": True, "customChartUrl": new_chart_url}


@router.delete("/{trade_id}", response_model=ApiResponse)
async def delete_trade_entry(
    trade_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Permanently deletes a trade entry from user's journal."""
    repo = TradeRepository(db)
    deleted = await repo.delete_by_id_and_user(trade_id, current_user.id)
    if not deleted:
        raise NotFoundError(f"معامله با شناسه {trade_id} یافت نشد.")
    return ApiResponse(success=True, message="معامله با موفقیت حذف شد.")
