import re
import time
from typing import List, Dict, Any, Optional
import httpx

from app.core.dynamic_config import DynamicConfig
from app.core.logger import logger
from app.database.seed import DEFAULT_PAIRS
from app.services.market_service import MarketService

_EXCLUDED_PAIR_RE = re.compile(
    r"^(USDC|FDUSD|TUSD|USDP|BUSD|DAI|EUR|GBP|AUD|TRY|BRL|ARS|PAXG|AEUR|USDE|EURI)USDT$"
    r"|.*(UP|DOWN|BULL|BEAR)USDT$",
    re.IGNORECASE,
)

_EXTRA_META = {
    "DOGEUSDT": {"icon": "Ð", "color": "text-amber-300 bg-amber-500/10"},
    "ADAUSDT": {"icon": "₳", "color": "text-sky-400 bg-sky-500/10"},
    "AVAXUSDT": {"icon": "▲", "color": "text-rose-400 bg-rose-500/10"},
    "LINKUSDT": {"icon": "⬡", "color": "text-blue-400 bg-blue-500/10"},
    "SUIUSDT": {"icon": "💧", "color": "text-cyan-400 bg-cyan-500/10"},
    "PEPEUSDT": {"icon": "🐸", "color": "text-emerald-400 bg-emerald-500/10"},
    "TRXUSDT": {"icon": "◈", "color": "text-red-400 bg-red-500/10"},
    "LTCUSDT": {"icon": "Ł", "color": "text-slate-300 bg-slate-500/10"},
}
_PAIR_META = {
    **{p["symbol"]: {"icon": p["icon"], "color": p["color"], "step": p["step"]} for p in DEFAULT_PAIRS},
    **_EXTRA_META,
}
_BADGE_COLORS = [
    "text-blue-400 bg-blue-500/10",
    "text-emerald-400 bg-emerald-500/10",
    "text-purple-400 bg-purple-500/10",
    "text-amber-400 bg-amber-500/10",
    "text-cyan-400 bg-cyan-500/10",
    "text-rose-400 bg-rose-500/10",
]
_BINANCE_24HR_ENDPOINTS = (
    "https://api.binance.com/api/v3/ticker/24hr",
    "https://data-api.binance.vision/api/v3/ticker/24hr",
)


def format_pair_price(raw: Any) -> str:
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return "0.00"
    if num <= 0:
        return "0.00"
    if num < 0.001:
        return f"{num:.8f}"
    if num < 0.1:
        return f"{num:.6f}"
    if num < 10:
        return f"{num:.4f}"
    return f"{num:.2f}"


def infer_price_step(raw: Any) -> float:
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return 1.0
    if num <= 0:
        return 1.0
    if num >= 10000:
        return 50.0
    if num >= 1000:
        return 5.0
    if num >= 100:
        return 1.0
    if num >= 10:
        return 0.1
    if num >= 1:
        return 0.01
    if num >= 0.01:
        return 0.001
    if num >= 0.0001:
        return 0.00001
    return 0.0000001


class PairService:
    """Centralized service providing the unified active exchange pairs list and live tickers."""

    _cached_pairs: List[Dict[str, Any]] = []
    _cache_ts: float = 0.0
    _CACHE_TTL_SEC: int = 120

    @classmethod
    def _build_pair_item(cls, symbol: str, last_price: Any, change_pct: Any = 0.0) -> Dict[str, Any]:
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        meta = _PAIR_META.get(symbol, {})
        color_idx = sum(ord(ch) for ch in base) % len(_BADGE_COLORS)
        return {
            "symbol": symbol,
            "label": f"{base} / USDT",
            "base": base,
            "icon": meta.get("icon") or base[:2],
            "color": meta.get("color") or _BADGE_COLORS[color_idx],
            "defaultPrice": format_pair_price(last_price),
            "step": meta.get("step") or infer_price_step(last_price),
            "change_pct": round(float(change_pct or 0.0), 2),
        }

    @classmethod
    async def get_active_pairs(cls, limit: int = 300, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Returns the exact same major active USDT pairs used in the React Mini-App."""
        now = time.time()
        if not force_refresh and cls._cached_pairs and (now - cls._cache_ts) < cls._CACHE_TTL_SEC:
            return cls._cached_pairs[:limit]

        async with httpx.AsyncClient(timeout=6.0) as client:
            for url in _BINANCE_24HR_ENDPOINTS:
                try:
                    res = await client.get(url)
                    if res.status_code != 200:
                        continue
                    tickers = res.json()
                    if not isinstance(tickers, list):
                        continue

                    filtered = []
                    for t in tickers:
                        sym = t.get("symbol", "")
                        if not sym.endswith("USDT") or _EXCLUDED_PAIR_RE.match(sym):
                            continue
                        try:
                            price = float(t.get("lastPrice") or 0)
                            vol = float(t.get("quoteVolume") or 0)
                        except (TypeError, ValueError):
                            continue
                        if price > 0 and vol > 100000:
                            filtered.append((vol, sym, price, t.get("priceChangePercent") or 0.0))

                    if filtered:
                        filtered.sort(key=lambda x: x[0], reverse=True)
                        cls._cached_pairs = [
                            cls._build_pair_item(sym, price, chg)
                            for _, sym, price, chg in filtered[:300]
                        ]
                        cls._cache_ts = now
                        return cls._cached_pairs[:limit]
                except Exception as exc:
                    logger.debug(f"PairService endpoint {url} failed: {exc}")

        if cls._cached_pairs:
            return cls._cached_pairs[:limit]

        fallback = DynamicConfig.get("supported_pairs", DEFAULT_PAIRS) or DEFAULT_PAIRS
        return [
            {
                **p,
                "defaultPrice": str(p.get("defaultPrice") or p.get("default_price") or "0.00"),
                "change_pct": 0.0,
            }
            for p in fallback[:limit]
        ]

    @classmethod
    async def find_pair(cls, raw_query: str) -> Optional[Dict[str, Any]]:
        """Matches a typed symbol/coin name (e.g., 'BTC', 'btcusdt', 'SOL/USDT') against active pairs."""
        q = (raw_query or "").strip().upper().replace(" / ", "").replace("/", "").replace(" ", "")
        if not q:
            return None
        pairs = await cls.get_active_pairs()
        for p in pairs:
            if p["symbol"] == q or p["base"] == q:
                return p
        target_sym = q if q.endswith("USDT") else f"{q}USDT"
        for p in pairs:
            if p["symbol"] == target_sym:
                return p
        return None

    @classmethod
    async def get_pair_ticker(cls, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetches current live price and 24h percentage change for a single pair."""
        norm = (symbol or "").strip().upper().replace(" / ", "").replace("/", "").replace(" ", "")
        if not norm.endswith("USDT"):
            norm += "USDT"

        async with httpx.AsyncClient(timeout=5.0) as client:
            for base_url in _BINANCE_24HR_ENDPOINTS:
                try:
                    res = await client.get(base_url, params={"symbol": norm})
                    if res.status_code == 200:
                        data = res.json()
                        price = float(data.get("lastPrice") or 0)
                        if price > 0:
                            return {
                                "symbol": norm,
                                "price": price,
                                "price_str": format_pair_price(price),
                                "change_pct": round(float(data.get("priceChangePercent") or 0.0), 2),
                            }
                except Exception:
                    continue

        # CCXT fallback
        try:
            pair_key = f"{norm[:-4]}/{norm[-4:]}"
            ticker = await MarketService.get_exchange().fetch_ticker(pair_key)
            price = float(ticker.get("last") or ticker.get("close") or 0)
            if price > 0:
                return {
                    "symbol": norm,
                    "price": price,
                    "price_str": format_pair_price(price),
                    "change_pct": round(float(ticker.get("percentage") or 0.0), 2),
                }
        except Exception as exc:
            logger.warning(f"PairService ticker fallback failed for {norm}: {exc}")

        # Cached pair fallback
        cached = next((p for p in cls._cached_pairs if p["symbol"] == norm), None)
        if cached:
            return {
                "symbol": norm,
                "price": float(cached["defaultPrice"]),
                "price_str": cached["defaultPrice"],
                "change_pct": float(cached.get("change_pct") or 0.0),
            }
        return None
