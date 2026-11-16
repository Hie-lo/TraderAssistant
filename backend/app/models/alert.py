from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Integer, String, Numeric, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class PriceAlert(Base):
    """Smart price and percentage alerts."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'PRICE' or 'PERCENT'
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # 'UP' or 'DOWN'
    base_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    trigger_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, index=True)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="alerts")
