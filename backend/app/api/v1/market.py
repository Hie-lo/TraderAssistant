import asyncio
import html
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_vip_role
from app.core.config import settings
from app.core.exceptions import BusinessValidationError
from app.core.logger import logger
from app.core.security import AuthenticatedUser
from app.services.market_service import MarketService

router = APIRouter(prefix="/market", tags=["Market"])

ALLOWED_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}


async def _notify_admin_exchange_error(error_details: str, symbol: str, timeframe: str) -> None:
    """Best-effort async Telegram notification to Admin on exchange API outages."""
    if not settings.BOT_TOKEN or "Placeholder" in settings.BOT_TOKEN:
        return

    target_chat = settings.ADMIN_LOG_CHANNEL_ID
    if not target_chat or str(target_chat) == "-1001234567890":
        target_chat = settings.SUPER_ADMIN_IDS[0] if settings.SUPER_ADMIN_IDS else None
    if not target_chat:
        return

    safe_err = html.escape(error_details[:400])
    text = f"🚨 <b>Exchange API Error:</b> <code>{safe_err}</code>\n({html.escape(symbol)} | {html.escape(timeframe)})"

    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"chat_id": target_chat, "text": text, "parse_mode": "HTML"})
    except Exception as notify_exc:
        logger.warning(f"Failed to deliver admin exchange error alert: {notify_exc}")


@router.get("/klines")
async def get_superchart_klines(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=30),
    timeframe: str = Query("15m"),
    limit: int = Query(200, ge=20, le=500),
    current_user: AuthenticatedUser = Depends(require_vip_role),
):
    """Strict VIP-only live OHLCV endpoint for Superchart with fail-safe 503 + admin alert."""
    norm_symbol = symbol.replace(" / ", "").replace("/", "").strip().upper()
    if not norm_symbol.isalnum():
        raise BusinessValidationError("نماد معاملاتی نامعتبر است.")

    tf = (timeframe or "15m").strip().lower()
    if tf not in ALLOWED_TIMEFRAMES:
        raise BusinessValidationError("تایم‌فریم نامعتبر است.")

    try:
        bars = await MarketService.fetch_live_ohlcv_strict(
            symbol=norm_symbol,
            timeframe=tf,
            limit=limit,
        )
        return {"symbol": norm_symbol, "timeframe": tf, "bars": bars}
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error(f"Superchart klines fetch failed ({norm_symbol} {tf}, user={current_user.id}): {err_msg}")
        asyncio.create_task(_notify_admin_exchange_error(err_msg, norm_symbol, tf))
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch market data from exchange. Please try again shortly.",
        )
