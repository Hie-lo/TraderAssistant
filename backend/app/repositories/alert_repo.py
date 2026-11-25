from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.alert import PriceAlert
from app.repositories.base_repo import BaseRepository


class AlertRepository(BaseRepository[PriceAlert]):
    """Repository handling price alerts."""

    def __init__(self, session: AsyncSession):
        super().__init__(PriceAlert, session)

    async def get_active_alerts(self) -> List[PriceAlert]:
        stmt = select(PriceAlert).where(PriceAlert.is_triggered == False).order_by(PriceAlert.created_at.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def count_active_by_user(self, user_id: int) -> int:
        stmt = select(func.count(PriceAlert.id)).where(PriceAlert.user_id == user_id, PriceAlert.is_triggered == False)
        res = await self.session.execute(stmt)
        return int(res.scalar() or 0)

    async def mark_as_triggered(self, alert_id: int) -> Optional[PriceAlert]:
        alert = await self.get_by_id(alert_id)
        if alert:
            alert.is_triggered = True
            alert.triggered_at = datetime.now(timezone.utc)
            await self.session.commit()
        return alert

    async def list_by_user(self, user_id: int, limit: int = 50) -> List[PriceAlert]:
        stmt = select(PriceAlert).where(PriceAlert.user_id == user_id).order_by(PriceAlert.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def delete_by_id_and_user(self, alert_id: int, user_id: int) -> bool:
        stmt = select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == user_id)
        res = await self.session.execute(stmt)
        alert = res.scalar_one_or_none()
        if not alert:
            return False
        await self.session.delete(alert)
        await self.session.commit()
        return True
