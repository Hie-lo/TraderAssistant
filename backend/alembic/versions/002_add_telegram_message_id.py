"""002_add_telegram_message_id

Revision ID: 002_add_telegram_message_id
Revises: 001_initial
Create Date: 2026-11-25 00:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_add_telegram_message_id"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("telegram_message_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("trades", "telegram_message_id")
