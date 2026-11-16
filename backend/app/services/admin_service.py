from datetime import datetime, timedelta, timezone
from typing import Optional, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.repositories.system_repo import SystemRepository
from app.core.access_control import AccessControl
from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import NotFoundError, BusinessValidationError
from app.core.logger import logger


class AdminService:
    """Business logic for administrative actions, user moderation, and config controls."""

    @classmethod
    async def change_user_status(
        cls,
        session: AsyncSession,
        admin_id: int,
        target_user_id: int,
        new_status: str,
        ban_reason: Optional[str] = None,
        duration_minutes: Optional[int] = None
    ) -> User:
        user_repo = UserRepository(session)
        system_repo = SystemRepository(session)

        user = await user_repo.get_by_id(target_user_id)
        if not user:
            raise NotFoundError(f"کاربری با شناسه {target_user_id} یافت نشد.")

        valid_statuses = ["ACTIVE", "RESTRICTED", "TEMP_BANNED", "BANNED"]
        new_status = new_status.upper()
        if new_status not in valid_statuses:
            raise BusinessValidationError(f"وضعیت {new_status} معتبر نمی‌باشد.")

        banned_until: Optional[datetime] = None
        if new_status == "TEMP_BANNED":
            mins = duration_minutes or 15
            banned_until = datetime.now(timezone.utc) + timedelta(minutes=mins)

        updated_user = await user_repo.update_status(
            user_id=target_user_id,
            status=new_status,
            ban_reason=ban_reason,
            banned_until=banned_until
        )

        # Update in-memory AccessControl cache
        AccessControl.set_user_restriction(
            user_id=target_user_id,
            status=new_status,
            banned_until=banned_until,
            ban_reason=ban_reason,
            role=user.role
        )

        # Audit log
        await system_repo.add_audit_log(
            admin_id=admin_id,
            action=f"SET_USER_{new_status}",
            target_id=str(target_user_id),
            details={
                "previous_status": user.status,
                "new_status": new_status,
                "ban_reason": ban_reason,
                "duration_minutes": duration_minutes
            }
        )
        logger.info(f"Admin {admin_id} changed user {target_user_id} status to {new_status}")
        return updated_user

    @classmethod
    async def update_dynamic_config(
        cls,
        session: AsyncSession,
        admin_id: int,
        key: str,
        value: Any,
        description: Optional[str] = None
    ) -> None:
        await DynamicConfig.set(
            session=session,
            key=key,
            value=value,
            admin_id=admin_id,
            description=description
        )
