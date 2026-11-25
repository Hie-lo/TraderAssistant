from typing import Optional, Any
from decimal import Decimal, InvalidOperation
from pydantic import Field, field_validator
from app.schemas.common import CamelModel


def _parse_optional_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned in ("", "—", "-", "null", "undefined", "None"):
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid numeric value: {value}") from exc
    raise ValueError(f"Unsupported numeric type: {type(value).__name__}")


class TradeCreateSchema(CamelModel):
    """Schema for creating a trade from calculator input (accepts raw numbers or numeric strings)."""

    pair: str
    base: Optional[str] = None
    is_long: bool = Field(..., alias="isLong")
    entry_price: Decimal = Field(..., alias="entryPrice")
    stop_loss: Optional[Decimal] = Field(default=None, alias="stopLoss")
    take_profit: Optional[Decimal] = Field(default=None, alias="takeProfit")
    leverage: int = Field(default=10, ge=1, le=2000)
    balance: Optional[Decimal] = None
    risk_type: Optional[str] = Field(default="%", alias="riskType")
    risk_value: Optional[Decimal] = Field(default=Decimal("2"), alias="riskValue")
    size: Optional[Decimal] = None
    margin: Optional[Decimal] = None
    risk_amount: Optional[Decimal] = Field(default=None, alias="riskAmount")
    potential_profit: Optional[Decimal] = Field(default=None, alias="potentialProfit")
    rr: Optional[str] = None
    status: Optional[str] = "OPEN"
    strategy: Optional[str] = "Price Action"
    entry_reason: Optional[str] = Field(default="", alias="entryReason")
    notes: Optional[str] = ""
    chart_timeframe: Optional[str] = Field(default="15m", alias="chartTimeframe")

    @field_validator("entry_price", mode="before")
    @classmethod
    def coerce_required_decimal(cls, v: Any) -> Decimal:
        parsed = _parse_optional_decimal(v)
        if parsed is None:
            raise ValueError("قیمت ورود (entry_price) الزامی است.")
        return parsed

    @field_validator(
        "stop_loss",
        "take_profit",
        "balance",
        "risk_value",
        "size",
        "margin",
        "risk_amount",
        "potential_profit",
        mode="before",
    )
    @classmethod
    def coerce_optional_decimal(cls, v: Any) -> Optional[Decimal]:
        return _parse_optional_decimal(v)


class TradeUpdateSchema(CamelModel):
    """Schema for updating trade dirty state (status, notes, strategy, chart)."""

    status: Optional[str] = None  # 'OPEN', 'TP', 'SL', 'DRAW'
    strategy: Optional[str] = None
    entry_reason: Optional[str] = Field(default=None, alias="entryReason")
    notes: Optional[str] = None
    chart_timeframe: Optional[str] = Field(default=None, alias="chartTimeframe")
    has_chart_snapshot: Optional[bool] = Field(default=None, alias="hasChartSnapshot")


class TradeResponseSchema(CamelModel):
    """Schema for trade returned to React frontend."""

    id: str
    pair: str
    base: str
    is_long: bool = Field(..., alias="isLong")
    entry_price: str = Field(..., alias="entryPrice")
    stop_loss: str = Field(..., alias="stopLoss")
    take_profit: str = Field(..., alias="takeProfit")
    size: str
    margin: str
    leverage: int
    risk_amount: str = Field(..., alias="riskAmount")
    potential_profit: str = Field(..., alias="potentialProfit")
    rr: str
    status: str
    strategy: str
    entry_reason: str = Field(..., alias="entryReason")
    notes: str
    date: str
    has_chart_snapshot: bool = Field(default=False, alias="hasChartSnapshot")
    chart_timeframe: str = Field(default="15m", alias="chartTimeframe")
    custom_chart_url: Optional[str] = Field(default=None, alias="customChartUrl")
    is_custom_chart: bool = Field(default=False, alias="isCustomChart")
    realized_pnl: Optional[str] = Field(default="0.00", alias="realizedPnl")
    telegram_message_id: Optional[int] = Field(default=None, alias="telegramMessageId")
