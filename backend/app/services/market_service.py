from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime
import pandas as pd
import ccxt.async_support as ccxt_async
from app.core.logger import logger


class MarketService:
    """Singleton exchange client using ccxt.async_support with graceful fallback."""

    _exchange: Optional[ccxt_async.binance] = None

    @classmethod
    def get_exchange(cls) -> ccxt_async.binance:
        if cls._exchange is None:
            cls._exchange = ccxt_async.binance({
                "enableRateLimit": True,
                "timeout": 8000,
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
    async def fetch_ohlcv_dataframe(
        cls,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 80,
        center_price: Optional[float] = None
    ) -> pd.DataFrame:
        """Fetches OHLCV candles from Binance and returns a formatted pandas DataFrame."""
        exchange = cls.get_exchange()
        # Clean symbol format e.g. BTCUSDT -> BTC/USDT and lowercase timeframe (1H -> 1h)
        norm_symbol = symbol.replace(" / ", "").replace("/", "").upper()
        pair_key = f"{norm_symbol[:-4]}/{norm_symbol[-4:]}"
        tf_ccxt = (timeframe or "15m").lower()

        try:
            raw_candles = await exchange.fetch_ohlcv(pair_key, timeframe=tf_ccxt, limit=limit)
        except Exception as e:
            logger.warning(f"CCXT fetch_ohlcv failed for {symbol}: {e}. Generating fallback candles.")
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
