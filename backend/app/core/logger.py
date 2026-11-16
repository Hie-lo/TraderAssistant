import os
import sys
import time
import hashlib
import traceback
from typing import Optional, Dict
from loguru import logger
import httpx
from app.core.config import settings

# Create logs directory
os.makedirs(settings.LOGS_DIR, exist_ok=True)

# Configure Loguru
logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    os.path.join(settings.LOGS_DIR, "app.log"),
    rotation="00:00",
    retention="14 days",
    compression="zip",
    encoding="utf-8",
    level="INFO"
)
logger.add(
    os.path.join(settings.LOGS_DIR, "error.log"),
    rotation="00:00",
    retention="30 days",
    compression="zip",
    encoding="utf-8",
    level="ERROR"
)


class TelegramLogNotifier:
    """Sends throttled, deduplicated error notifications to Telegram Admin Channel."""

    _last_sent_timestamps: Dict[str, float] = {}
    _cooldown_seconds: float = 300.0  # 5 minutes throttle per error signature

    @classmethod
    def _compute_error_hash(cls, location: str, exc_type: str, message: str) -> str:
        raw = f"{location}:{exc_type}:{message}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    async def notify_admin_channel(
        cls,
        trace_id: str,
        section: str,
        exc: Exception,
        user_info: Optional[str] = None,
        extra_info: Optional[str] = None
    ) -> bool:
        if not settings.BOT_TOKEN or not settings.ADMIN_LOG_CHANNEL_ID or "Placeholder" in settings.BOT_TOKEN:
            return False

        exc_type = type(exc).__name__
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_snippet = "".join(tb_lines[-8:]) if tb_lines else str(exc)
        
        # Deduplication check
        err_hash = cls._compute_error_hash(section, exc_type, str(exc))
        now = time.time()
        last_sent = cls._last_sent_timestamps.get(err_hash, 0.0)
        if now - last_sent < cls._cooldown_seconds:
            logger.debug(f"Error notification throttled for hash {err_hash}")
            return False

        cls._last_sent_timestamps[err_hash] = now

        user_str = user_info or "سیستم / تسک پس‌زمینه"
        text = (
            f"🚨 <b>گزارش خطای سیستم</b> (<code>#{trace_id}</code>)\n\n"
            f"📍 <b>بخش:</b> <code>{section}</code>\n"
            f"👤 <b>کاربر:</b> {user_str}\n"
            f"⚠️ <b>نوع خطا:</b> <code>{exc_type}: {str(exc)[:120]}</code>\n"
        )
        if extra_info:
            text += f"ℹ️ <b>اطلاعات تکمیلی:</b> {extra_info}\n"

        text += f"\n📋 <b>Traceback:</b>\n<pre>{tb_snippet[:800]}</pre>"

        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.ADMIN_LOG_CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to send telegram error notification: {e}")
            return False
