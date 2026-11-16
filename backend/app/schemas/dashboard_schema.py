from typing import List, Optional, Any, Dict
from app.schemas.common import CamelModel
from app.schemas.trade_schema import TradeResponseSchema


class UserProfileSchema(CamelModel):
    """User summary included in initial bootstrap."""
    id: int
    first_name: str
    default_balance: str
    discipline_badge: str
    status: str
    role: str = "USER"


class ConfigPairSchema(CamelModel):
    """Pair definition for UI selection."""
    symbol: str
    label: str
    base: str
    icon: str
    color: str
    default_price: str
    step: float


class DynamicAppConfigSchema(CamelModel):
    """Dynamic configuration values passed to frontend."""
    max_leverage: int
    pairs: List[ConfigPairSchema]
    default_strategies: List[str]


class BootstrapResponseSchema(CamelModel):
    """Unified payload returned by GET /api/v1/bootstrap."""
    user: UserProfileSchema
    config: DynamicAppConfigSchema
    custom_strategies: List[str]
    trades: List[TradeResponseSchema]
