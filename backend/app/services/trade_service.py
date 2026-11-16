from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timezone
import jdatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.models.user import User
from app.schemas.trade_schema import TradeCreateSchema, TradeUpdateSchema, TradeResponseSchema
from app.repositories.trade_repo import TradeRepository
from app.repositories.user_repo import UserRepository
from app.services.calculator_service import CalculatorService
from app.services.chart_service import ChartService
from app.core.exceptions import NotFoundError, BusinessValidationError
from app.core.logger import logger


class TradeService:
    """Business logic for trade journal entries, dirty state persistence, and stats."""

    @staticmethod
    def _format_jalali_date(dt: datetime) -> str:
        """Converts datetime to Persian Jalali readable string."""
        if not dt:
            return "الان"
        try:
            jdt = jdatetime.datetime.fromgregorian(datetime=dt)
            return jdt.strftime("%Y/%m/%d - %H:%M")
        except Exception:
            return dt.strftime("%Y/%m/%d - %H:%M")

    @classmethod
    def trade_to_response(cls, trade: Trade) -> TradeResponseSchema:
        """Serializes Trade ORM model to TradeResponseSchema for React Mini-App."""
        sl_str = f"{trade.stop_loss:f}".rstrip("0").rstrip(".") if trade.stop_loss else "—"
        tp_str = f"{trade.take_profit:f}".rstrip("0").rstrip(".") if trade.take_profit else "—"
        entry_str = f"{trade.entry_price:f}".rstrip("0").rstrip(".")
        size_str = f"{trade.position_size:.4f}"
        margin_str = f"{trade.required_margin:.2f}"
        risk_str = f"{trade.risk_amount:.2f}"
        profit_str = f"{trade.potential_profit:.2f}" if trade.potential_profit else risk_str
        rr_str = f"{trade.rr_ratio:.2f}" if trade.rr_ratio else "—"
        pnl_str = f"{trade.realized_pnl:+.2f}" if trade.status in ["TP", "SL"] else "$0.00"

        return TradeResponseSchema(
            id=str(trade.id),
            pair=trade.pair,
            base=trade.base_asset,
            is_long=trade.is_long,
            entry_price=entry_str,
            stop_loss=sl_str,
            take_profit=tp_str,
            size=size_str,
            margin=margin_str,
            leverage=trade.leverage,
            risk_amount=risk_str,
            potential_profit=profit_str,
            rr=rr_str,
            status=trade.status,
            strategy=trade.strategy_name,
            entry_reason=trade.entry_reason or "",
            notes=trade.notes or "",
            date=cls._format_jalali_date(trade.created_at),
            has_chart_snapshot=trade.has_chart_snapshot,
            chart_timeframe=trade.chart_timeframe,
            custom_chart_url=trade.chart_image_url,
            realized_pnl=pnl_str
        )

    @classmethod
    async def create_trade(
        cls,
        session: AsyncSession,
        user_id: int,
        trade_in: TradeCreateSchema
    ) -> Tuple[Trade, Optional[Decimal]]:
        """Validates calculations, persists trade record, and updates user default balance."""
        user_repo = UserRepository(session)
        trade_repo = TradeRepository(session)

        user = await user_repo.get_by_id(user_id)
        current_balance = Decimal(str(trade_in.balance)) if trade_in.balance else (user.default_balance if user else Decimal("1000.00"))

        calc_result = CalculatorService.calculate_position(
            balance=current_balance,
            risk_value=trade_in.risk_value,
            risk_type=trade_in.risk_type or "%",
            entry_price=trade_in.entry_price,
            stop_loss=trade_in.stop_loss,
            take_profit=trade_in.take_profit,
            leverage=trade_in.leverage,
            is_long=trade_in.is_long
        )

        # Update user default balance if provided
        if trade_in.balance and Decimal(str(trade_in.balance)) > 0:
            await user_repo.update_balance(user_id, Decimal(str(trade_in.balance)))

        norm_symbol = trade_in.pair.replace(" / ", "").replace("/", "").upper()
        if "USDT" not in norm_symbol:
            norm_symbol += "USDT"

        trade = Trade(
            user_id=user_id,
            pair=trade_in.pair,
            symbol=norm_symbol,
            base_asset=trade_in.base,
            is_long=trade_in.is_long,
            entry_price=Decimal(str(trade_in.entry_price)),
            stop_loss=Decimal(str(trade_in.stop_loss)) if trade_in.stop_loss and trade_in.stop_loss != "—" else None,
            take_profit=Decimal(str(trade_in.take_profit)) if trade_in.take_profit and trade_in.take_profit != "—" else None,
            position_size=calc_result.position_size,
            position_value=calc_result.position_value,
            required_margin=calc_result.required_margin,
            leverage=trade_in.leverage,
            risk_amount=calc_result.risk_amount,
            potential_profit=calc_result.potential_profit,
            rr_ratio=calc_result.rr_ratio,
            status="OPEN",
            realized_pnl=Decimal("0.00"),
            strategy_name=trade_in.strategy or "Price Action",
            entry_reason=trade_in.entry_reason or "",
            notes=trade_in.notes or "",
            has_chart_snapshot=True,
            chart_timeframe=trade_in.chart_timeframe or "1H",
            is_custom_chart=False
        )

        saved_trade = await trade_repo.create(trade)
        logger.info(f"Created trade {saved_trade.id} for user {user_id}: {saved_trade.pair} ({'LONG' if saved_trade.is_long else 'SHORT'})")
        return saved_trade, current_balance

    @classmethod
    async def update_trade_dirty_state(
        cls,
        session: AsyncSession,
        user_id: int,
        trade_id: str,
        patch_data: TradeUpdateSchema
    ) -> Tuple[Trade, bool]:
        """
        Updates dirty state fields sent from frontend.
        Returns (trade, needs_sl_check: bool).
        """
        trade_repo = TradeRepository(session)
        trade = await trade_repo.get_by_id_and_user(trade_id, user_id)
        if not trade:
            raise NotFoundError("معامله مورد نظر یافت نشد.")

        needs_sl_check = False
        fields_to_update = {}

        # 1. Status change and Realized PnL calculation
        if patch_data.status is not None and patch_data.status != trade.status:
            new_status = patch_data.status.upper()
            if new_status not in ["OPEN", "TP", "SL", "DRAW"]:
                raise BusinessValidationError("وضعیت معامله نامعتبر است.")

            fields_to_update["status"] = new_status
            if new_status == "TP":
                fields_to_update["realized_pnl"] = trade.potential_profit or trade.risk_amount
                fields_to_update["closed_at"] = datetime.now(timezone.utc)
            elif new_status == "SL":
                fields_to_update["realized_pnl"] = -trade.risk_amount
                fields_to_update["closed_at"] = datetime.now(timezone.utc)
                needs_sl_check = True
            elif new_status == "DRAW":
                fields_to_update["realized_pnl"] = Decimal("0.00")
                fields_to_update["closed_at"] = datetime.now(timezone.utc)
            elif new_status == "OPEN":
                fields_to_update["realized_pnl"] = Decimal("0.00")
                fields_to_update["closed_at"] = None

        if patch_data.strategy is not None:
            fields_to_update["strategy_name"] = patch_data.strategy

        if patch_data.entry_reason is not None:
            fields_to_update["entry_reason"] = patch_data.entry_reason

        if patch_data.notes is not None:
            fields_to_update["notes"] = patch_data.notes

        if patch_data.chart_timeframe is not None:
            fields_to_update["chart_timeframe"] = patch_data.chart_timeframe

        if patch_data.has_chart_snapshot is not None:
            fields_to_update["has_chart_snapshot"] = patch_data.has_chart_snapshot
            if not patch_data.has_chart_snapshot:
                # User removed snapshot
                ChartService.remove_chart_file(trade.chart_image_url)
                fields_to_update["chart_image_url"] = None

        updated_trade = await trade_repo.update_fields(trade, fields_to_update)
        logger.info(f"Updated trade dirty state for {trade_id}: {list(fields_to_update.keys())}")
        return updated_trade, needs_sl_check

    @classmethod
    def calculate_portfolio_stats(cls, trades: List[Trade]) -> Dict[str, Any]:
        """Calculates win rate, best strategy, total closed trades, and net realized PnL."""
        closed = [t for t in trades if t.status in ["TP", "SL"]]
        wins = [t for t in closed if t.status == "TP"]
        losses = [t for t in closed if t.status == "SL"]

        win_rate = int(round((len(wins) / len(closed) * 100))) if closed else 0
        total_pnl = sum((t.realized_pnl for t in trades), Decimal("0.00"))

        # Strategy performance
        strat_counts: Dict[str, int] = {}
        strat_wins: Dict[str, int] = {}
        for t in trades:
            s = t.strategy_name
            strat_counts[s] = strat_counts.get(s, 0) + 1
            if t.status == "TP":
                strat_wins[s] = strat_wins.get(s, 0) + 1

        best_strategy = "Price Action"
        best_rate = -1.0
        for s, count in strat_counts.items():
            rate = strat_wins.get(s, 0) / count
            if rate > best_rate and count >= 1:
                best_rate = rate
                best_strategy = s

        return {
            "total_trades": len(trades),
            "closed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_realized_pnl": f"{total_pnl:+.2f}",
            "best_strategy": best_strategy
        }
