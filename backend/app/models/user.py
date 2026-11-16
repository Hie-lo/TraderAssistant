from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, String, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class User(Base):
    """User table holding identity, telegram ID, access role, and risk defaults."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="USER", nullable=False)  # 'USER', 'VIP', 'ADMIN'
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)  # 'ACTIVE', 'RESTRICTED', 'TEMP_BANNED', 'BANNED'
    banned_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    default_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("1000.00"), nullable=False)
    custom_drawdown_limit_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    strategies = relationship("UserStrategy", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("PriceAlert", back_populates="user", cascade="all, delete-orphan")
