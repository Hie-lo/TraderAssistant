from typing import Optional, List, Dict, Any, Callable, Awaitable
import asyncio
import json
import time
from datetime import datetime
import aiohttp
import httpx
import pandas as pd
import ccxt.async_support as ccxt_async
from app.core.logger import logger

_BYBIT_INTERVALS = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
    "1d": "D",
}

_KUCOIN_INTERVALS = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1hour",
    "4h": "4hour",
    "1d": "1day",
}


class MarketService:
    """Singleton exchange client using ccxt.async_support with graceful fallback."""

    _exchange: Optional[ccxt_async.binance] = None

    @classmethod
    def get_exchange(cls) -> ccxt_async.binance:
        if cls._exchange is None:
            cls._exchange = ccxt_async.binance({
                "enableRateLimit": True,
                "timeout": 12000,
                "options": {
                    "defaultType": "future"
                }
            })
        return cls._exchange

    @classmethod
    async def close(cls) -> None:
        """Closes exchange aiohttp session on application shutdown."""
        if cls._exchange:
            try:
                await cls._exchange.close()
                logger.info("Closed ccxt exchange connection.")
            except Exception as e:
                logger.warning(f"Error closing ccxt exchange: {e}")
            finally:
                cls._exchange = None

    @classmethod
    async def _fetch_raw_exchange_klines(
        cls,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 80,
        end_time: Optional[int] = None,
    ) -> List[List[float]]:
        """Fetches raw OHLCV candles from Binance via CCXT with public REST klines fallback."""
        exchange = cls.get_exchange()
        norm_symbol = symbol.replace(" / ", "").replace("/", "").upper()
        if not norm_symbol.endswith("USDT"):
            norm_symbol += "USDT"
        pair_key = f"{norm_symbol[:-4]}/{norm_symbol[-4:]}"
        tf_ccxt = (timeframe or "15m").lower()
        ccxt_params = {"endTime": int(end_time)} if end_time is not None else {}

        raw_candles = None
        last_error: Optional[Exception] = None
        try:
            raw_candles = await exchange.fetch_ohlcv(pair_key, timeframe=tf_ccxt, limit=limit, params=ccxt_params)
        except Exception as e:
            last_error = e
            logger.warning(f"CCXT fetch_ohlcv failed for {symbol} ({tf_ccxt}): {e}. Trying Binance REST klines.")

        if not raw_candles:
            raw_candles, last_error = await cls._fetch_rest_klines_with_fallback(
                norm_symbol=norm_symbol,
                tf_ccxt=tf_ccxt,
                limit=limit,
                end_time=end_time,
                last_error=last_error,
            )

        if not raw_candles:
            raise RuntimeError(str(last_error) if last_error else f"Empty OHLCV payload for {norm_symbol}")

        if end_time is not None:
            raw_candles = [c for c in raw_candles if int(c[0]) <= int(end_time)]
        raw_candles.sort(key=lambda c: int(c[0]))
        return raw_candles

    @classmethod
    async def _fetch_rest_klines_with_fallback(
        cls,
        norm_symbol: str,
        tf_ccxt: str,
        limit: int,
        end_time: Optional[int],
        last_error: Optional[Exception] = None,
    ) -> tuple[Optional[List[List[float]]], Optional[Exception]]:
        """Tries Binance REST, Bybit v5, then KuCoin public REST klines in order."""
        binance_urls = (
            "https://fapi.binance.com/fapi/v1/klines",
            "https://api.binance.com/api/v3/klines",
            "https://data-api.binance.vision/api/v3/klines",
        )
        rest_params: Dict[str, Any] = {"symbol": norm_symbol, "interval": tf_ccxt, "limit": limit}
        if end_time is not None:
            rest_params["endTime"] = int(end_time)

        async with httpx.AsyncClient(timeout=4.0) as client:
            for url in binance_urls:
                try:
                    resp = await client.get(url, params=rest_params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if isinstance(rows, list) and rows:
                            return [
                                [int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])]
                                for k in rows
                            ], last_error
                    else:
                        last_error = RuntimeError(f"HTTP {resp.status_code} from {url}")
                except Exception as rest_err:
                    last_error = rest_err

            # Fallback 1: Bybit v5 public linear klines
            bybit_tf = _BYBIT_INTERVALS.get(tf_ccxt, "15")
            bybit_params: Dict[str, Any] = {
                "category": "linear",
                "symbol": norm_symbol,
                "interval": bybit_tf,
                "limit": min(limit, 200),
            }
            if end_time is not None:
                bybit_params["end"] = int(end_time)
            try:
                resp = await client.get("https://api.bybit.com/v5/market/kline", params=bybit_params)
                if resp.status_code == 200:
                    rows = (resp.json().get("result") or {}).get("list") or []
                    if rows:
                        return [
                            [int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])]
                            for k in rows
                        ], last_error
            except Exception as bybit_err:
                last_error = bybit_err

            # Fallback 2: KuCoin public spot klines
            kucoin_tf = _KUCOIN_INTERVALS.get(tf_ccxt, "15min")
            kucoin_sym = f"{norm_symbol[:-4]}-{norm_symbol[-4:]}"
            kucoin_params: Dict[str, Any] = {"symbol": kucoin_sym, "type": kucoin_tf}
            if end_time is not None:
                kucoin_params["endAt"] = int(end_time // 1000)
            try:
                resp = await client.get("https://api.kucoin.com/api/v1/market/candles", params=kucoin_params)
                if resp.status_code == 200:
                    rows = resp.json().get("data") or []
                    if rows:
                        return [
                            [int(k[0]) * 1000, float(k[1]), float(k[3]), float(k[4]), float(k[2]), float(k[5])]
                            for k in rows[:limit]
                        ], last_error
            except Exception as kucoin_err:
                last_error = kucoin_err

        return None, last_error

    @classmethod
    async def stream_exchange_klines(
        cls,
        symbol: str,
        timeframe: str,
        on_tick: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Resilient infinite exchange WebSocket consumer with multi-exchange fallback:
        Binance WS -> Bybit v5 WS -> KuCoin WS -> Multi-Exchange REST polling.
        """
        norm_symbol = symbol.replace(" / ", "").replace("/", "").upper()
        if not norm_symbol.endswith("USDT"):
            norm_symbol += "USDT"
        tf = (timeframe or "15m").strip().lower()
        last_log_ts = 0.0

        async def _dispatch_tick(source: str, tick: Dict[str, Any]) -> None:
            nonlocal last_log_ts
            raw_ts = int(tick["timestamp"])
            normalized = {
                "timestamp": raw_ts * 1000 if 0 < raw_ts < 1_000_000_000_000 else raw_ts,
                "open": float(tick["open"]),
                "high": float(tick["high"]),
                "low": float(tick["low"]),
                "close": float(tick["close"]),
                "volume": float(tick["volume"]),
            }
            now = time.monotonic()
            if now - last_log_ts >= 5.0:
                last_log_ts = now
                logger.info(f"Received live tick from exchange ({source} | {norm_symbol} {tf}): {normalized}")
            await on_tick(normalized)

        backoff_sec = 1.0
        ws_timeout = aiohttp.ClientTimeout(total=None, sock_connect=5.0, sock_read=15.0)
        while True:
            got_live_tick = False
            try:
                async with aiohttp.ClientSession(timeout=ws_timeout) as session:
                    # 1. Try Bybit v5 Public Linear WS first (fast, rarely geo-blocked), then Binance Spot/Futures WS
                    bybit_tf = _BYBIT_INTERVALS.get(tf, "15")
                    bybit_topic = f"kline.{bybit_tf}.{norm_symbol}"
                    try:
                        async with session.ws_connect("wss://stream.bybit.com/v5/public/linear", heartbeat=20.0) as ws:
                            await ws.send_json({"op": "subscribe", "args": [bybit_topic]})
                            backoff_sec = 1.0
                            logger.info(f"Connected exchange WS: Bybit ({norm_symbol} {tf})")
                            while True:
                                msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    payload = json.loads(msg.data)
                                    if payload.get("topic") == bybit_topic:
                                        for item in payload.get("data") or []:
                                            got_live_tick = True
                                            await _dispatch_tick(
                                                "bybit",
                                                {
                                                    "timestamp": int(item["start"]),
                                                    "open": float(item["open"]),
                                                    "high": float(item["high"]),
                                                    "low": float(item["low"]),
                                                    "close": float(item["close"]),
                                                    "volume": float(item["volume"]),
                                                },
                                            )
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                                    break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.warning(f"Bybit WS skipped/stalled ({norm_symbol} {tf}): {exc}")

                    # 2. Fallback to Binance Spot / Futures WebSockets
                    for ws_url in (
                        f"wss://stream.binance.com:9443/ws/{norm_symbol.lower()}@kline_{tf}",
                        f"wss://fstream.binance.com/ws/{norm_symbol.lower()}@kline_{tf}",
                    ):
                        try:
                            async with session.ws_connect(ws_url, heartbeat=20.0) as ws:
                                backoff_sec = 1.0
                                logger.info(f"Connected exchange WS fallback: Binance ({norm_symbol} {tf})")
                                while True:
                                    msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                                    if msg.type == aiohttp.WSMsgType.TEXT:
                                        k = (json.loads(msg.data)).get("k")
                                        if k:
                                            got_live_tick = True
                                            await _dispatch_tick(
                                                "binance",
                                                {
                                                    "timestamp": int(k["t"]),
                                                    "open": float(k["o"]),
                                                    "high": float(k["h"]),
                                                    "low": float(k["l"]),
                                                    "close": float(k["c"]),
                                                    "volume": float(k["v"]),
                                                },
                                            )
                                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                                        break
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            logger.warning(f"Binance WS skipped/stalled ({ws_url}): {exc}")

                    # 3. Fallback to KuCoin Public WebSocket
                    try:
                        async with session.post("https://api.kucoin.com/api/v1/bullet-public", timeout=aiohttp.ClientTimeout(total=5.0)) as token_resp:
                            if token_resp.status == 200:
                                token_data = (await token_resp.json()).get("data") or {}
                                token = token_data.get("token")
                                servers = token_data.get("instanceServers") or []
                                if token and servers:
                                    ep = servers[0]["endpoint"]
                                    kucoin_sym = f"{norm_symbol[:-4]}-{norm_symbol[-4:]}"
                                    kucoin_tf = _KUCOIN_INTERVALS.get(tf, "15min")
                                    topic = f"/market/candles:{kucoin_sym}_{kucoin_tf}"
                                    async with session.ws_connect(f"{ep}?token={token}", heartbeat=18.0) as ws:
                                        await ws.send_json({"id": str(int(time.time() * 1000)), "type": "subscribe", "topic": topic, "response": True})
                                        backoff_sec = 1.0
                                        logger.info(f"Connected exchange WS fallback: KuCoin ({norm_symbol} {tf})")
                                        while True:
                                            msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                                            if msg.type == aiohttp.WSMsgType.TEXT:
                                                payload = json.loads(msg.data)
                                                candles = ((payload.get("data") or {}).get("candles")) if payload.get("topic") == topic else None
                                                if candles and len(candles) >= 6:
                                                    got_live_tick = True
                                                    await _dispatch_tick(
                                                        "kucoin",
                                                        {
                                                            "timestamp": int(candles[0]) * 1000,
                                                            "open": float(candles[1]),
                                                            "high": float(candles[3]),
                                                            "low": float(candles[4]),
                                                            "close": float(candles[2]),
                                                            "volume": float(candles[5]),
                                                        },
                                                    )
                                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                                                break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.warning(f"KuCoin WS skipped/stalled ({norm_symbol} {tf}): {exc}")

                # 4. Multi-exchange REST poll cycle if outbound WS delivered no ticks
                if not got_live_tick:
                    bars = await cls.fetch_live_ohlcv_strict(symbol=norm_symbol, timeframe=tf, limit=2)
                    if bars:
                        await _dispatch_tick("rest_fallback", bars[-1])
            except asyncio.CancelledError:
                raise
            except Exception as loop_exc:
                logger.error(f"Exchange stream consumer error ({norm_symbol} {tf}): {loop_exc}")

            await asyncio.sleep(backoff_sec)
            backoff_sec = min(backoff_sec * 1.5, 5.0)

    @classmethod
    async def fetch_live_ohlcv_strict(
        cls,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 200,
        before_timestamp: Optional[int] = None,
    ) -> List[Dict[str, float]]:
        """Strictly fetches live OHLCV bars for Superchart; raises on exchange failure without fake candles."""
        end_time = int(before_timestamp) - 1 if before_timestamp is not None else None
        raw_candles = await cls._fetch_raw_exchange_klines(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            end_time=end_time,
        )
        return [
            {
                "timestamp": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            }
            for c in raw_candles
            if before_timestamp is None or int(c[0]) < int(before_timestamp)
        ]

    @classmethod
    async def fetch_ohlcv_dataframe(
        cls,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 80,
        center_price: Optional[float] = None
    ) -> pd.DataFrame:
        """Fetches OHLCV candles from Binance and returns a formatted pandas DataFrame."""
        tf_ccxt = (timeframe or "15m").lower()
        try:
            raw_candles = await cls._fetch_raw_exchange_klines(symbol=symbol, timeframe=tf_ccxt, limit=limit)
        except Exception as e:
            logger.warning(f"All exchange OHLCV sources failed for {symbol} ({tf_ccxt}): {e}. Generating fallback candles.")
            now_ms = int(datetime.now().timestamp() * 1000)
            tf_ms_map = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}
            step_ms = tf_ms_map.get(tf_ccxt, 900_000)
            raw_candles = []
            base_p = float(center_price) if center_price and center_price > 0 else (
                64000.0 if "BTC" in symbol else 3400.0 if "ETH" in symbol else 150.0
            )
            delta = base_p * 0.0015
            for i in range(limit):
                t = now_ms - (limit - i) * step_ms
                o = base_p + ((i % 5) - 2) * delta
                h = o + delta * 1.4
                l = o - delta * 1.4
                c = o + ((i % 3) - 1) * delta
                v = 100.0
                raw_candles.append([t, o, h, l, c, v])

        df = pd.DataFrame(
            raw_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        return df

    @classmethod
    async def fetch_price(cls, symbol: str) -> Optional[float]:
        """Fetches latest ticker price for symbol."""
        exchange = cls.get_exchange()
        norm_symbol = symbol.replace(" / ", "").replace("/", "").upper()
        pair_key = f"{norm_symbol[:-4]}/{norm_symbol[-4:]}"
        try:
            ticker = await exchange.fetch_ticker(pair_key)
            return float(ticker.get("last") or ticker.get("close") or 0.0)
        except Exception as e:
            logger.warning(f"Failed to fetch live price for {symbol}: {e}")
            return None

    @classmethod
    async def get_market_screener(cls, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Returns price and 24h change overview for top trading pairs."""
        target_symbols = symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "TON/USDT", "XRP/USDT"]
        exchange = cls.get_exchange()
        results = []

        for sym in target_symbols:
            try:
                ticker = await exchange.fetch_ticker(sym)
                last_price = float(ticker.get("last") or 0.0)
                change_pct = float(ticker.get("percentage") or 0.0)
                results.append({
                    "symbol": sym,
                    "price": f"{last_price:,.2f}" if last_price >= 1 else f"{last_price:.4f}",
                    "change_pct": round(change_pct, 2),
                    "high": float(ticker.get("high") or 0.0),
                    "low": float(ticker.get("low") or 0.0)
                })
            except Exception:
                results.append({
                    "symbol": sym,
                    "price": "N/A",
                    "change_pct": 0.0,
                    "high": 0.0,
                    "low": 0.0
                })
        return results
