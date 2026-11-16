import time
import asyncio
from datetime import datetime, timedelta, timezone
from collections import deque
from typing import Dict, Optional
from app.core.dynamic_config import DynamicConfig
from app.core.access_control import AccessControl
from app.core.exceptions import RateLimitExceeded
from app.core.logger import logger, TelegramLogNotifier


class RateLimiter:
    """In-memory sliding window rate limiter with anti-spam auto-shield mechanism."""

    _general_requests: Dict[int, deque] = {}
    _heavy_requests: Dict[int, deque] = {}

    @classmethod
    def check_rate_limit(cls, user_id: int, is_heavy: bool = False, username: Optional[str] = None) -> None:
        now = time.time()

        # 1. Initialize user deque if not present
        if user_id not in cls._general_requests:
            cls._general_requests[user_id] = deque()

        user_deque = cls._general_requests[user_id]

        # 2. Check Auto-Ban Shield (Burst threshold over 10 seconds)
        auto_ban_threshold = DynamicConfig.get("auto_ban_threshold_per_10s", 50)
        ten_seconds_ago = now - 10.0
        burst_count = sum(1 for t in user_deque if t >= ten_seconds_ago)

        if burst_count >= auto_ban_threshold:
            banned_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            ban_reason = f"طوفان درخواست ({burst_count} درخواست در ۱۰ ثانیه) - مسدودی خودکار سپر امنیتی"
            AccessControl.set_user_restriction(
                user_id=user_id,
                status="TEMP_BANNED",
                banned_until=banned_until,
                ban_reason=ban_reason
            )
            logger.warning(f"User {user_id} auto-banned for 15 minutes due to request storm ({burst_count} req/10s).")

            # Fire async alert to admin telegram channel
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    TelegramLogNotifier.notify_admin_channel(
                        trace_id="SHIELD",
                        section="RATE_LIMITER / AUTO_SHIELD",
                        exc=Exception(ban_reason),
                        user_info=f"{user_id} (@{username or 'N/A'})",
                        extra_info=f"محرومیت تا: {banned_until.strftime('%H:%M:%S UTC')}"
                    )
                )
            except RuntimeError:
                pass

            raise RateLimitExceeded(
                message="سیستم ضد اسپم فعال شد. حساب کاربری شما به مدت ۱۵ دقیقه مسدود گردید.",
                retry_after=900
            )

        # 3. Standard API Rate Limit (Requests per minute)
        limit_per_min = DynamicConfig.get("api_rate_limit_per_min", 60)
        sixty_seconds_ago = now - 60.0

        # Purge older timestamps
        while user_deque and user_deque[0] < sixty_seconds_ago:
            user_deque.popleft()

        if len(user_deque) >= limit_per_min:
            logger.warning(f"Rate limit exceeded for user {user_id} ({len(user_deque)}/{limit_per_min} req/min).")
            raise RateLimitExceeded(
                message=f"سقف مجاز درخواست در دقیقه ({limit_per_min}) به اتمام رسید. لطفاً کمی صبر فرمایید.",
                retry_after=60
            )

        user_deque.append(now)

        # 4. Heavy Operation Rate Limit (Chart generation, upload)
        if is_heavy:
            if user_id not in cls._heavy_requests:
                cls._heavy_requests[user_id] = deque()

            heavy_deque = cls._heavy_requests[user_id]
            heavy_limit = DynamicConfig.get("heavy_rate_limit_per_min", 6)

            while heavy_deque and heavy_deque[0] < sixty_seconds_ago:
                heavy_deque.popleft()

            if len(heavy_deque) >= heavy_limit:
                logger.warning(f"Heavy rate limit exceeded for user {user_id} ({len(heavy_deque)}/{heavy_limit}).")
                raise RateLimitExceeded(
                    message=f"سقف مجاز عملیات سنگین (تولید یا آپلود چارت: {heavy_limit} بار در دقیقه) تکمیل شد.",
                    retry_after=60
                )

            heavy_deque.append(now)
