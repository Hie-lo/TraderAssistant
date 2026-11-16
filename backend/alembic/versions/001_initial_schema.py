"""001_initial_schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-11-16 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="USER"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ban_reason", sa.String(length=256), nullable=True),
        sa.Column("default_balance", sa.Numeric(precision=18, scale=2), nullable=False, server_default="1000.00"),
        sa.Column("custom_drawdown_limit_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)

    # 2. user_strategies
    op.create_table(
        "user_strategies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_strategy_name")
    )
    op.create_index(op.f("ix_user_strategies_user_id"), "user_strategies", ["user_id"], unique=False)

    # 3. trades
    op.create_table(
        "trades",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pair", sa.String(length=24), nullable=False),
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("base_asset", sa.String(length=12), nullable=False),
        sa.Column("is_long", sa.Boolean(), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("take_profit", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("position_size", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("position_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("required_margin", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("leverage", sa.Integer(), nullable=False),
        sa.Column("risk_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("potential_profit", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("rr_ratio", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
        sa.Column("realized_pnl", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0.00"),
        sa.Column("strategy_name", sa.String(length=64), nullable=False, server_default="Price Action"),
        sa.Column("entry_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("has_chart_snapshot", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("chart_timeframe", sa.String(length=8), nullable=False, server_default="1H"),
        sa.Column("chart_image_url", sa.String(length=512), nullable=True),
        sa.Column("is_custom_chart", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_trades_user_id"), "trades", ["user_id"], unique=False)
    op.create_index(op.f("ix_trades_symbol"), "trades", ["symbol"], unique=False)
    op.create_index(op.f("ix_trades_status"), "trades", ["status"], unique=False)
    op.create_index(op.f("ix_trades_created_at"), "trades", ["created_at"], unique=False)

    # 4. price_alerts
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("alert_type", sa.String(length=16), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("base_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("target_value", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("trigger_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("is_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_price_alerts_user_id"), "price_alerts", ["user_id"], unique=False)
    op.create_index(op.f("ix_price_alerts_symbol"), "price_alerts", ["symbol"], unique=False)
    op.create_index(op.f("ix_price_alerts_trigger_price"), "price_alerts", ["trigger_price"], unique=False)
    op.create_index(op.f("ix_price_alerts_is_triggered"), "price_alerts", ["is_triggered"], unique=False)

    # 5. system_settings
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    )

    # 6. admin_audit_logs
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
    op.drop_table("system_settings")
    op.drop_table("price_alerts")
    op.drop_table("trades")
    op.drop_table("user_strategies")
    op.drop_table("users")
