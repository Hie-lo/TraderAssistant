from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.trade import Trade
from app.repositories.base_repo import BaseRepository


class TradeRepository(BaseRepository[Trade]):
    """Repository handling Trade journal persistence and queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(Trade, session)

    async def get_by_id_and_user(self, trade_id: str, user_id: int) -> Optional[Trade]:
        stmt = select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_by_id_and_user(self, trade_id: str, user_id: int) -> bool:
        trade = await self.get_by_id_and_user(trade_id, user_id)
        if trade:
            await self.session.delete(trade)
            await self.session.commit()
            return True
        return False

    async def list_by_user(self, user_id: int, limit: int = 200) -> List[Trade]:
        stmt = select(Trade).where(Trade.user_id == user_id).order_by(Trade.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_fields(self, trade: Trade, fields: Dict[str, Any]) -> Trade:
        for k, v in fields.items():
            if hasattr(trade, k):
                setattr(trade, k, v)
        await self.session.commit()
        return trade

    async def get_weekly_losses(self, user_id: int) -> Decimal:
        """Returns total sum of risk_amount for trades closed as 'SL' in the past 7 days."""
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = select(func.coalesce(func.sum(Trade.risk_amount), 0)).where(
            Trade.user_id == user_id,
            Trade.status == "SL",
            Trade.created_at >= seven_days_ago
        )
        res = await self.session.execute(stmt)
        total_loss = res.scalar() or Decimal("0.00")
        return Decimal(str(total_loss))
