"""003_add_vip_subscriptions_and_payments

Revision ID: 003_vip_payments
Revises: 002_add_telegram_message_id
Create Date: 2026-11-25 16:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_vip_payments"
down_revision: Union[str, None] = "002_add_telegram_message_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("subscription_end_date", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_duration", sa.Integer(), nullable=False),
        sa.Column("receipt_image_url", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"], unique=False)
    op.create_index(op.f("ix_payments_status"), "payments", ["status"], unique=False)
    op.create_index(op.f("ix_payments_created_at"), "payments", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_column("users", "subscription_end_date")
