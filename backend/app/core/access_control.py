from typing import Dict, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.exceptions import UserBannedError, AuthorizationError
from app.core.logger import logger
from app.models.user import User


@dataclass
class UserAccessInfo:
    status: str  # 'ACTIVE', 'RESTRICTED', 'TEMP_BANNED', 'BANNED'
    banned_until: Optional[datetime] = None
    ban_reason: Optional[str] = None
    role: str = "USER"


class AccessControlManager:
    """In-memory cache for restricted and banned users to protect DB from spam."""

    _restricted_users: Dict[int, UserAccessInfo] = {}

    @classmethod
    async def load_restricted_users(cls, session: AsyncSession) -> None:
        """Loads all non-active users into in-memory access control cache."""
        result = await session.execute(
            select(User).where(User.status.in_(["BANNED", "TEMP_BANNED", "RESTRICTED"]))
        )
        users = result.scalars().all()
        for u in users:
            cls._restricted_users[u.id] = UserAccessInfo(
                status=u.status,
                banned_until=u.banned_until,
                ban_reason=u.ban_reason,
                role=u.role
            )
        logger.info(f"Loaded {len(cls._restricted_users)} restricted/banned users into memory.")

    @classmethod
    def set_user_restriction(
        cls,
        user_id: int,
        status: str,
        banned_until: Optional[datetime] = None,
        ban_reason: Optional[str] = None,
        role: str = "USER"
    ) -> None:
        """Updates in-memory restriction record for a user."""
        if status == "ACTIVE":
            cls._restricted_users.pop(user_id, None)
        else:
            cls._restricted_users[user_id] = UserAccessInfo(
                status=status,
                banned_until=banned_until,
                ban_reason=ban_reason,
                role=role
            )

    @classmethod
    def get_user_status(cls, user_id: int) -> Optional[UserAccessInfo]:
        """Returns in-memory access info for user if restricted, else None."""
        return cls._restricted_users.get(user_id)

    @classmethod
    def check_access(cls, user_id: int, is_heavy_or_write: bool = False) -> None:
        """
        Validates in-memory access permissions. Raises UserBannedError or AuthorizationError.
        Returns immediately in O(1) if active.
        """
        access_info = cls._restricted_users.get(user_id)
        if not access_info or access_info.status == "ACTIVE":
            return

        now = datetime.now(timezone.utc)

        if access_info.status == "BANNED":
            reason = access_info.ban_reason or "حساب کاربری شما به دستور مدیریت مسدود شده است."
            raise UserBannedError(message=f"دسترسی مسدود است: {reason}", ban_reason=reason)

        if access_info.status == "TEMP_BANNED":
            if access_info.banned_until and now < access_info.banned_until:
                remaining_seconds = int((access_info.banned_until - now).total_seconds())
                remaining_minutes = max(1, remaining_seconds // 60)
                reason = access_info.ban_reason or "محرومیت موقت به دلیل ارسال بیش از حد درخواست"
                raise UserBannedError(
                    message=f"حساب شما موقتاً مسدود است. مدت زمان باقی‌مانده: {remaining_minutes} دقیقه.",
                    ban_reason=reason,
                    banned_until=access_info.banned_until.isoformat()
                )
            else:
                # Ban expired - lift in memory
                cls._restricted_users.pop(user_id, None)
                logger.info(f"Temporary ban expired for user {user_id}. Access restored.")
                return

        if access_info.status == "RESTRICTED":
            if is_heavy_or_write:
                reason = access_info.ban_reason or "حساب شما در وضعیت محدود (فقط خواندنی) قرار دارد."
                raise AuthorizationError(
                    message=f"امکان انجام این عملیات وجود ندارد: {reason}"
                )


AccessControl = AccessControlManager
