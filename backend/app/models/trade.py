import uuid
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, String, Numeric, Integer, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Trade(Base):
    """Trade journal model matching frontend App.jsx data contract."""

    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pair: Mapped[str] = mapped_column(String(24), nullable=False)  # e.g. "BTC / USDT"
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)  # e.g. "BTCUSDT"
    base_asset: Mapped[str] = mapped_column(String(12), nullable=False)  # e.g. "BTC"
    is_long: Mapped[bool] = mapped_column(Boolean, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    take_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    position_size: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    position_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    required_margin: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    potential_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    rr_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)  # 'OPEN', 'TP', 'SL', 'DRAW'
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(64), default="Price Action", nullable=False)
    entry_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    has_chart_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    chart_timeframe: Mapped[str] = mapped_column(String(8), default="15m", nullable=False)  # '5m', '15m', '1H', '4H'
    chart_image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_custom_chart: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="trades")
