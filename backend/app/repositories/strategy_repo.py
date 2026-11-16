from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from app.models.strategy import UserStrategy
from app.models.trade import Trade
from app.repositories.base_repo import BaseRepository


class StrategyRepository(BaseRepository[UserStrategy]):
    """Repository handling custom user strategies."""

    def __init__(self, session: AsyncSession):
        super().__init__(UserStrategy, session)

    async def get_by_user(self, user_id: int) -> List[UserStrategy]:
        stmt = select(UserStrategy).where(UserStrategy.user_id == user_id).order_by(UserStrategy.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_by_user_and_name(self, user_id: int, name: str) -> Optional[UserStrategy]:
        stmt = select(UserStrategy).where(UserStrategy.user_id == user_id, UserStrategy.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_by_user_and_name(self, user_id: int, name: str) -> bool:
        strat = await self.get_by_user_and_name(user_id, name)
        if strat:
            await self.session.delete(strat)
            await self.session.commit()
            return True
        return False

    async def reassign_trades_strategy(self, user_id: int, old_strategy: str, new_strategy: str) -> int:
        stmt = (
            update(Trade)
            .where(Trade.user_id == user_id, Trade.strategy_name == old_strategy)
            .values(strategy_name=new_strategy)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount
