from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.system import SystemSetting
from app.core.logger import logger

DEFAULT_PAIRS = [
    {
        "symbol": "BTCUSDT",
        "label": "BTC / USDT",
        "base": "BTC",
        "icon": "₿",
        "color": "text-yellow-500 bg-yellow-500/10",
        "defaultPrice": "64250.00",
        "step": 50
    },
    {
        "symbol": "ETHUSDT",
        "label": "ETH / USDT",
        "base": "ETH",
        "icon": "Ξ",
        "color": "text-indigo-400 bg-indigo-500/10",
        "defaultPrice": "3420.00",
        "step": 5
    },
    {
        "symbol": "SOLUSDT",
        "label": "SOL / USDT",
        "base": "SOL",
        "icon": "◎",
        "color": "text-purple-400 bg-purple-500/10",
        "defaultPrice": "148.50",
        "step": 0.5
    },
    {
        "symbol": "BNBUSDT",
        "label": "BNB / USDT",
        "base": "BNB",
        "icon": "❖",
        "color": "text-amber-400 bg-amber-500/10",
        "defaultPrice": "585.00",
        "step": 1
    },
    {
        "symbol": "TONUSDT",
        "label": "TON / USDT",
        "base": "TON",
        "icon": "💎",
        "color": "text-sky-400 bg-sky-500/10",
        "defaultPrice": "5.45",
        "step": 0.05
    },
    {
        "symbol": "XRPUSDT",
        "label": "XRP / USDT",
        "base": "XRP",
        "icon": "✕",
        "color": "text-gray-300 bg-gray-500/10",
        "defaultPrice": "0.58",
        "step": 0.005
    }
]

DEFAULT_STRATEGIES = [
    "Price Action",
    "Smart Money / ICT",
    "Breakout",
    "RSI Divergence",
    "Support & Resistance",
    "Scalp / Momentum",
    "Fibonacci Retracement",
    "EMA Crossover",
    "Order Block / FVG",
    "Liquidity Sweep"
]

DEFAULT_SETTINGS: Dict[str, Any] = {
    "maintenance_mode": False,
    "max_leverage": 2000,
    "default_weekly_drawdown_pct": 5.0,
    "max_active_alerts_free": 5,
    "max_chart_upload_mb": 2.0,
    "api_rate_limit_per_min": 60,
    "heavy_rate_limit_per_min": 6,
    "auto_ban_threshold_per_10s": 50,
    "telegram_init_data_ttl_sec": 7200,
    "supported_pairs": DEFAULT_PAIRS,
    "default_strategies": DEFAULT_STRATEGIES
}


async def seed_initial_settings(session: AsyncSession) -> None:
    """Seeds the database with initial dynamic settings if they do not already exist."""
    created_count = 0
    for key, value in DEFAULT_SETTINGS.items():
        res = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
        if not res.scalar_one_or_none():
            setting = SystemSetting(
                key=key,
                value_json=value,
                description=f"Default system setting for {key}"
            )
            session.add(setting)
            created_count += 1

    if created_count > 0:
        await session.commit()
        logger.info(f"Seeded {created_count} default system settings into database.")
    else:
        logger.debug("System settings already seeded.")
