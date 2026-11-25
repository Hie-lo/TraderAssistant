from typing import Optional, List
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.trade import Trade
from app.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository handling User operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_or_create(
        self,
        telegram_id: int,
        first_name: str,
        username: Optional[str] = None,
        role: str = "USER"
    ) -> User:
        user = await self.get_by_id(telegram_id)
        if not user:
            user = User(
                id=telegram_id,
                first_name=first_name,
                username=username,
                role=role,
                status="ACTIVE",
                default_balance=Decimal("1000.00")
            )
            self.session.add(user)
            await self.session.commit()
        else:
            # Update last active timestamp, basic info, and promote role if SUPER_ADMIN_IDS updated
            user.last_active_at = datetime.now(timezone.utc)
            if role == "ADMIN" and user.role != "ADMIN":
                user.role = "ADMIN"
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            if username and user.username != username:
                user.username = username
            await self.session.commit()
        return user

    async def resolve_effective_role(self, user: Optional[User]) -> str:
        """Auto-downgrades expired VIP accounts back to USER while preserving ADMIN/active VIP."""
        if not user:
            return "USER"
        if user.role == "VIP" and user.subscription_end_date is not None:
            end_dt = user.subscription_end_date
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt <= datetime.now(timezone.utc):
                user.role = "USER"
                await self.session.commit()
                await self.session.refresh(user)
        return user.role

    async def update_vip_subscription(
        self,
        user: User,
        role: str,
        subscription_end_date: Optional[datetime]
    ) -> User:
        user.role = role
        user.subscription_end_date = subscription_end_date
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_balance(self, user_id: int, new_balance: Decimal) -> None:
        user = await self.get_by_id(user_id)
        if user and new_balance > 0:
            user.default_balance = new_balance
            await self.session.commit()

    async def get_by_id_for_update(self, user_id: int) -> Optional[User]:
        """Acquires a row-level lock on the user record to serialize concurrent quota checks."""
        stmt = select(User).where(User.id == user_id).with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def update_status(
        self,
        user_id: int,
        status: str,
        ban_reason: Optional[str] = None,
        banned_until: Optional[datetime] = None
    ) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.status = status
            user.ban_reason = ban_reason
            user.banned_until = banned_until
            await self.session.commit()
        return user

    async def list_users_with_trade_count(self, limit: int = 50, offset: int = 0) -> List[tuple[User, int]]:
        stmt = (
            select(User, func.count(Trade.id).label("trades_count"))
            .outerjoin(Trade, Trade.user_id == User.id)
            .group_by(User.id)
            .order_by(User.last_active_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [(row[0], int(row[1])) for row in res.all()]
