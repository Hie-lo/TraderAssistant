from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from app.database.session import AsyncSessionLocal
from app.repositories.user_repo import UserRepository


async def is_db_admin(user_id: int) -> bool:
    """Checks the database directly (users.role == 'ADMIN') as the single source of truth."""
    if not user_id:
        return False
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_id(user_id)
        return bool(user and user.role == "ADMIN")


class IsAdminFilter(BaseFilter):
    """Aiogram filter authorizing requests solely based on DB user.role == 'ADMIN'."""

    async def __call__(self, event: TelegramObject) -> bool:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return False
        return await is_db_admin(from_user.id)
