from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from app.core.access_control import AccessControl
from app.core.rate_limiter import RateLimiter
from app.core.exceptions import UserBannedError, RateLimitExceeded
from app.core.logger import logger


class BotAccessControlMiddleware(BaseMiddleware):
    """Enforces in-memory ban and rate limits before processing bot messages and callback queries."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        username = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username

        if user_id:
            try:
                # 1. In-memory ban check
                AccessControl.check_access(user_id=user_id, is_heavy_or_write=False)
                # 2. In-memory rate limit check
                RateLimiter.check_rate_limit(user_id=user_id, is_heavy=False, username=username)
            except UserBannedError as e:
                if isinstance(event, Message):
                    await event.answer(f"⛔ <b>دسترسی غیرمجاز:</b> {e.message}")
                elif isinstance(event, CallbackQuery):
                    await event.answer(f"⛔ {e.message}", show_alert=True)
                return
            except RateLimitExceeded as e:
                if isinstance(event, Message):
                    await event.answer(f"⏳ <b>محدودیت درخواست:</b> {e.message}")
                elif isinstance(event, CallbackQuery):
                    await event.answer(f"⏳ {e.message}", show_alert=True)
                return

        return await handler(event, data)
