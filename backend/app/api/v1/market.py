import asyncio
import html
import time
from typing import Dict, Optional, Set, Tuple
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
StreamKey = Tuple[str, str]


class ConnectionManager:
    """Manages active VIP WebSocket clients per (symbol, timeframe) and fans out exchange ticks."""

    def __init__(self) -> None:
        self._rooms: Dict[StreamKey, Set[WebSocket]] = {}
        self._tasks: Dict[StreamKey, asyncio.Task] = {}
        self._latest_ticks: Dict[StreamKey, dict] = {}
        self._last_sent_sig: Dict[StreamKey, tuple] = {}
        self._last_broadcast_log: Dict[StreamKey, float] = {}

    async def connect(self, websocket: WebSocket, symbol: str, timeframe: str) -> StreamKey:
        await websocket.accept()
        key: StreamKey = (symbol, timeframe)
        self._rooms.setdefault(key, set()).add(websocket)

        if key not in self._tasks or self._tasks[key].done():
            self._tasks[key] = asyncio.create_task(self._consume_exchange(key))

        # Send immediate initial candle frame if cached or via strict REST lookup
        cached = self._latest_ticks.get(key)
        if cached:
            await websocket.send_json(cached)
        else:
            try:
                bars = await MarketService.fetch_live_ohlcv_strict(symbol=symbol, timeframe=timeframe, limit=2)
                if bars:
                    latest = self._format_candle(bars[-1])
                    self._latest_ticks[key] = latest
                    await websocket.send_json(latest)
            except Exception as exc:
                logger.warning(f"Initial WS candle snapshot skipped ({symbol} {timeframe}): {exc}")

        return key

    async def disconnect(self, websocket: WebSocket, key: StreamKey) -> None:
        clients = self._rooms.get(key)
        if clients:
            clients.discard(websocket)
            if not clients:
                self._rooms.pop(key, None)
                self._last_sent_sig.pop(key, None)
                self._last_broadcast_log.pop(key, None)
                task = self._tasks.pop(key, None)
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    @staticmethod
    def _format_candle(raw: dict) -> dict:
        raw_ts = int(raw["timestamp"])
        ts_ms = raw_ts * 1000 if 0 < raw_ts < 1_000_000_000_000 else raw_ts
        return {
            "timestamp": ts_ms,
            "open": float(raw["open"]),
            "high": float(raw["high"]),
            "low": float(raw["low"]),
            "close": float(raw["close"]),
            "volume": float(raw["volume"]),
        }

    async def broadcast(self, key: StreamKey, raw_candle: dict) -> None:
        candle = self._format_candle(raw_candle)
        sig = (
            candle["timestamp"],
            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"],
            candle["volume"],
        )
        if sig == self._last_sent_sig.get(key):
            return
        self._last_sent_sig[key] = sig
        self._latest_ticks[key] = candle

        active_connections = list(self._rooms.get(key, ()))
        if not active_connections:
            return

        now = time.monotonic()
        if now - self._last_broadcast_log.get(key, 0.0) >= 5.0:
            self._last_broadcast_log[key] = now
            logger.info(f"Broadcasting to {len(active_connections)} clients ({key[0]} {key[1]})")

        dead_sockets = []
        for ws in active_connections:
            try:
                await ws.send_json(candle)
            except Exception:
                dead_sockets.append(ws)

        for ws in dead_sockets:
            await self.disconnect(ws, key)

    async def _consume_exchange(self, key: StreamKey) -> None:
        symbol, timeframe = key
        try:
            await MarketService.stream_exchange_klines(
                symbol=symbol,
                timeframe=timeframe,
                on_tick=lambda tick: self.broadcast(key, tick),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Exchange stream task exited unexpectedly ({symbol} {timeframe}): {exc}")

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        self._rooms.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


connection_manager = ConnectionManager()


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
    """VIP-gated WebSocket endpoint managed via ConnectionManager with clean disconnect handling."""
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

    stream_key = await connection_manager.connect(websocket, norm_symbol, tf)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await connection_manager.disconnect(websocket, stream_key)
