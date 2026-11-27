import asyncio
import html
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.api.deps import require_vip_role
from app.core.config import settings
from app.core.exceptions import AuthenticationError, BusinessValidationError
from app.core.logger import logger
from app.core.security import AuthenticatedUser, verify_telegram_init_data
from app.database.session import AsyncSessionLocal
from app.repositories.user_repo import UserRepository
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


def _normalize_symbol_and_tf(symbol: str, timeframe: str) -> tuple[str, str]:
    norm_symbol = symbol.replace(" / ", "").replace("/", "").strip().upper()
    if not norm_symbol.isalnum():
        raise BusinessValidationError("نماد معاملاتی نامعتبر است.")

    tf = (timeframe or "15m").strip().lower()
    if tf not in ALLOWED_TIMEFRAMES:
        raise BusinessValidationError("تایم‌فریم نامعتبر است.")
    return norm_symbol, tf


@router.get("/klines")
async def get_superchart_klines(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=30),
    timeframe: str = Query("15m"),
    limit: int = Query(200, ge=20, le=500),
    before_timestamp: Optional[int] = Query(None, gt=0),
    current_user: AuthenticatedUser = Depends(require_vip_role),
):
    """Strict VIP-only live & paginated OHLCV endpoint for Superchart with fail-safe 503 + admin alert."""
    norm_symbol, tf = _normalize_symbol_and_tf(symbol, timeframe)

    try:
        bars = await MarketService.fetch_live_ohlcv_strict(
            symbol=norm_symbol,
            timeframe=tf,
            limit=limit,
            before_timestamp=before_timestamp,
        )
        return {
            "symbol": norm_symbol,
            "timeframe": tf,
            "bars": bars,
            "hasMore": len(bars) >= limit,
        }
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error(f"Superchart klines fetch failed ({norm_symbol} {tf}, user={current_user.id}): {err_msg}")
        asyncio.create_task(_notify_admin_exchange_error(err_msg, norm_symbol, tf))
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch market data from exchange. Please try again shortly.",
        )


@router.websocket("/stream")
async def stream_superchart_klines(
    websocket: WebSocket,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("15m"),
    init_data: Optional[str] = Query(None),
):
    """VIP-gated WebSocket pushing real-time latest active candle updates for Superchart."""
    try:
        user = verify_telegram_init_data(init_data)
        norm_symbol, tf = _normalize_symbol_and_tf(symbol, timeframe)
    except (AuthenticationError, BusinessValidationError):
        await websocket.close(code=4401)
        return

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_id(user.id)
        if db_user is None:
            is_allowed = user.role == "ADMIN" or user.id in settings.SUPER_ADMIN_IDS
        else:
            effective_role = "ADMIN" if user.role == "ADMIN" else await user_repo.resolve_effective_role(db_user)
            is_allowed = effective_role in ("VIP", "ADMIN")

    if not is_allowed:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    last_sent = None

    try:
        while True:
            try:
                latest_bars = await MarketService.fetch_live_ohlcv_strict(
                    symbol=norm_symbol,
                    timeframe=tf,
                    limit=2,
                )
                if latest_bars:
                    latest = latest_bars[-1]
                    candle_payload = {
                        "timestamp": int(latest["timestamp"]),
                        "open": float(latest["open"]),
                        "high": float(latest["high"]),
                        "low": float(latest["low"]),
                        "close": float(latest["close"]),
                        "volume": float(latest["volume"]),
                    }
                    sig = (
                        candle_payload["timestamp"],
                        candle_payload["open"],
                        candle_payload["high"],
                        candle_payload["low"],
                        candle_payload["close"],
                        candle_payload["volume"],
                    )
                    if sig != last_sent:
                        last_sent = sig
                        await websocket.send_json(candle_payload)
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.warning(f"WebSocket market stream poll error ({norm_symbol} {tf}): {exc}")

            await asyncio.sleep(1.5)
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
