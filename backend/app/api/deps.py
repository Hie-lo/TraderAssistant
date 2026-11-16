from typing import AsyncGenerator, Optional
from fastapi import Header, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.core.security import verify_telegram_init_data, AuthenticatedUser
from app.core.access_control import AccessControl
from app.core.rate_limiter import RateLimiter
from app.core.exceptions import AuthorizationError, MaintenanceModeActive
from app.core.dynamic_config import DynamicConfig
from app.core.config import settings


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency supplying an async SQLAlchemy session per HTTP request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
) -> AuthenticatedUser:
    """
    Validates Telegram WebApp signature, applies maintenance mode,
    checks in-memory ban status, and enforces rate limits.
    """
    # 1. Authenticate user from header
    user = verify_telegram_init_data(x_telegram_init_data)

    # 2. Check Maintenance Mode
    is_admin = user.role == "ADMIN" or user.id in settings.SUPER_ADMIN_IDS
    if DynamicConfig.get("maintenance_mode", False) and not is_admin:
        raise MaintenanceModeActive()

    # 3. Check In-Memory Ban & Restriction
    is_write = request.method not in ["GET", "HEAD", "OPTIONS"]
    AccessControl.check_access(user.id, is_heavy_or_write=is_write)

    # 4. Standard Rate Limit Check
    RateLimiter.check_rate_limit(user.id, is_heavy=False, username=user.username)

    return user


async def require_admin(
    user: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """Enforces that the current authenticated user has administrative privileges."""
    if user.role != "ADMIN" and user.id not in settings.SUPER_ADMIN_IDS:
        raise AuthorizationError("دسترسی به بخش مدیریت فقط برای ادمین‌های سیستم مجاز است.")
    return user


def check_heavy_limit(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Enforces strict rate limits on heavy CPU/IO endpoints (chart generation & upload)."""
    RateLimiter.check_rate_limit(user.id, is_heavy=True, username=user.username)
    return user
