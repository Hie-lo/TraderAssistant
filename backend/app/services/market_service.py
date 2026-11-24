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
        timeframe: str = "1h",
        limit: int = 80
    ) -> pd.DataFrame:
        """Fetches OHLCV candles from Binance and returns a formatted pandas DataFrame."""
        exchange = cls.get_exchange()
        # Clean symbol format e.g. BTCUSDT -> BTC/USDT and lowercase timeframe (1H -> 1h)
        norm_symbol = symbol.replace(" / ", "").replace("/", "").upper()
        pair_key = f"{norm_symbol[:-4]}/{norm_symbol[-4:]}"
        tf_ccxt = (timeframe or "1h").lower()

        try:
            raw_candles = await exchange.fetch_ohlcv(pair_key, timeframe=tf_ccxt, limit=limit)
        except Exception as e:
            logger.warning(f"CCXT fetch_ohlcv failed for {symbol}: {e}. Generating fallback candles.")
            # Generate deterministic fallback candle data if exchange is offline or blocked
            now_ms = int(datetime.now().timestamp() * 1000)
            step_ms = 3600 * 1000 if tf_ccxt == "1h" else (14400 * 1000 if tf_ccxt == "4h" else 900 * 1000)
            raw_candles = []
            base_p = 64000.0 if "BTC" in symbol else 3400.0 if "ETH" in symbol else 150.0
            for i in range(limit):
                t = now_ms - (limit - i) * step_ms
                o = base_p + (i % 5) * 10
                h = o + 25
                l = o - 25
                c = o + ((i % 3) - 1) * 15
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
