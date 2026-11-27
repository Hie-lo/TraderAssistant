import asyncio
import html
import json
import time
from typing import Optional
import aiohttp
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
    last_emit_time = 0.0
    min_emit_interval = 0.10  # Throttle micro-ticks to max ~10 updates/sec

    async def _emit_candle(raw_candle: dict) -> None:
        nonlocal last_sent, last_emit_time
        raw_ts = int(raw_candle["timestamp"])
        ts_ms = raw_ts * 1000 if 0 < raw_ts < 1_000_000_000_000 else raw_ts
        candle_payload = {
            "timestamp": ts_ms,
            "open": float(raw_candle["open"]),
            "high": float(raw_candle["high"]),
            "low": float(raw_candle["low"]),
            "close": float(raw_candle["close"]),
            "volume": float(raw_candle["volume"]),
        }
        sig = (
            candle_payload["timestamp"],
            candle_payload["open"],
            candle_payload["high"],
            candle_payload["low"],
            candle_payload["close"],
            candle_payload["volume"],
        )
        now = time.monotonic()
        if sig == last_sent:
            return
        if last_sent is not None and (now - last_emit_time) < min_emit_interval:
            return
        last_sent = sig
        last_emit_time = now
        await websocket.send_json(candle_payload)

    try:
        # 1. Push initial snapshot immediately before entering real-time loop
        try:
            initial_bars = await MarketService.fetch_live_ohlcv_strict(
                symbol=norm_symbol,
                timeframe=tf,
                limit=2,
            )
            if initial_bars:
                await _emit_candle(initial_bars[-1])
        except WebSocketDisconnect:
            raise
        except Exception as init_exc:
            logger.warning(f"Initial WebSocket kline snapshot failed ({norm_symbol} {tf}): {init_exc}")

        # 2. Primary real-time stream via Binance WS with throttled emission
        stream_urls = (
            f"wss://fstream.binance.com/ws/{norm_symbol.lower()}@kline_{tf}",
            f"wss://stream.binance.com:9443/ws/{norm_symbol.lower()}@kline_{tf}",
        )
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            while True:
                streamed = False
                for ws_url in stream_urls:
                    try:
                        async with session.ws_connect(ws_url, heartbeat=20.0) as binance_ws:
                            streamed = True
                            async for msg in binance_ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    payload = json.loads(msg.data)
                                    k = payload.get("k")
                                    if k:
                                        await _emit_candle(
                                            {
                                                "timestamp": int(k["t"]),
                                                "open": float(k["o"]),
                                                "high": float(k["h"]),
                                                "low": float(k["l"]),
                                                "close": float(k["c"]),
                                                "volume": float(k["v"]),
                                            }
                                        )
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                    except WebSocketDisconnect:
                        raise
                    except Exception as binance_exc:
                        logger.debug(f"Binance WS stream fallback ({ws_url}): {binance_exc}")

                # 3. Fallback polling if outbound Binance WS is unreachable
                if not streamed:
                    try:
                        latest_bars = await MarketService.fetch_live_ohlcv_strict(
                            symbol=norm_symbol,
                            timeframe=tf,
                            limit=2,
                        )
                        if latest_bars:
                            await _emit_candle(latest_bars[-1])
                    except WebSocketDisconnect:
                        raise
                    except Exception as poll_exc:
                        logger.warning(f"WebSocket market stream poll error ({norm_symbol} {tf}): {poll_exc}")

                await asyncio.sleep(1.5)
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
