from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Payment(Base):
    """VIP subscription payment receipts submitted by users and reviewed by admins."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_duration: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 3, or 6 months
    receipt_image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False, index=True)  # PENDING, APPROVED, REJECTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="payments")
