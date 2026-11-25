from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payment import Payment
from app.models.user import User
from app.repositories.base_repo import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Repository managing VIP subscription payment receipts."""

    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)

    async def list_by_user(self, user_id: int, limit: int = 20) -> List[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_with_users(
        self, status_filter: Optional[str] = "PENDING", limit: int = 100
    ) -> List[Tuple[Payment, Optional[User]]]:
        stmt = (
            select(Payment, User)
            .outerjoin(User, Payment.user_id == User.id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        if status_filter:
            stmt = stmt.where(Payment.status == status_filter.upper())
        res = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]
