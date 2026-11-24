from typing import Optional
from decimal import Decimal
from pydantic import Field
from app.schemas.common import CamelModel


class TradeCreateSchema(CamelModel):
    """Schema for creating a trade from calculator input."""

    pair: str
    base: str
    is_long: bool = Field(..., alias="isLong")
    entry_price: str = Field(..., alias="entryPrice")
    stop_loss: Optional[str] = Field(default="—", alias="stopLoss")
    take_profit: Optional[str] = Field(default="—", alias="takeProfit")
    leverage: int = Field(default=10, ge=1, le=2000)
    balance: Optional[str] = None
    risk_type: Optional[str] = Field(default="%", alias="riskType")
    risk_value: Optional[str] = Field(default="2", alias="riskValue")
    strategy: Optional[str] = "Price Action"
    entry_reason: Optional[str] = Field(default="", alias="entryReason")
    notes: Optional[str] = ""
    chart_timeframe: Optional[str] = Field(default="1H", alias="chartTimeframe")


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
    chart_timeframe: str = Field(default="1H", alias="chartTimeframe")
    custom_chart_url: Optional[str] = Field(default=None, alias="customChartUrl")
    realized_pnl: Optional[str] = Field(default="0.00", alias="realizedPnl")
    telegram_message_id: Optional[int] = Field(default=None, alias="telegramMessageId")
