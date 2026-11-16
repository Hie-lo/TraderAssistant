from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.system import SystemSetting, AdminAuditLog
from app.repositories.base_repo import BaseRepository


class SystemRepository(BaseRepository[SystemSetting]):
    """Repository handling system dynamic settings and audit logs."""

    def __init__(self, session: AsyncSession):
        super().__init__(SystemSetting, session)

    async def get_all_settings(self) -> List[SystemSetting]:
        stmt = select(SystemSetting)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_audit_log(
        self,
        admin_id: int,
        action: str,
        details: Any,
        target_id: Optional[str] = None
    ) -> AdminAuditLog:
        audit = AdminAuditLog(
            admin_id=admin_id,
            action=action,
            target_id=target_id,
            details_json=details
        )
        self.session.add(audit)
        await self.session.commit()
        return audit

    async def list_recent_audit_logs(self, limit: int = 50) -> List[AdminAuditLog]:
        stmt = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
