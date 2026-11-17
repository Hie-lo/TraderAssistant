import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl, unquote
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.core.config import settings
from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import AuthenticationError
from app.core.logger import logger


class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = False


class AuthenticatedUser(BaseModel):
    id: int
    first_name: str
    username: Optional[str] = None
    photo_url: Optional[str] = None
    role: str = "USER"
    is_mock: bool = False


def verify_telegram_init_data(init_data_raw: Optional[str]) -> AuthenticatedUser:
    """
    Validates Telegram WebApp initData HMAC-SHA256 signature and checks auth_date expiration.
    In development mode (ENV_MODE=development), allows DEV_MOCK_USER or empty headers.
    """
    # 1. Development Mode Mocking
    is_dev = settings.ENV_MODE.lower() == "development"
    if is_dev and (not init_data_raw or init_data_raw in ("DEV_MOCK_USER", "test", "null", "undefined")):
        return AuthenticatedUser(
            id=111111111,
            first_name="امیرحسین",
            username="amir_trader",
            role="ADMIN",
            is_mock=True
        )

    if not init_data_raw:
        raise AuthenticationError("هدر X-Telegram-Init-Data ارسال نشده است.")

    try:
        parsed_data = dict(parse_qsl(init_data_raw, keep_blank_values=True))
    except Exception as e:
        raise AuthenticationError(f"قالب initData نامعتبر است: {e}")

    received_hash = parsed_data.pop("hash", None)
    if not received_hash:
        raise AuthenticationError("فیلد hash در داده‌های تلگرام یافت نشد.")

    # 2. Replay Attack / Expiration Check
    auth_date_raw = parsed_data.get("auth_date")
    if not auth_date_raw or not auth_date_raw.isdigit():
        raise AuthenticationError("فیلد auth_date نامعتبر است.")

    auth_date = int(auth_date_raw)
    ttl = DynamicConfig.get("telegram_init_data_ttl_sec", 7200)
    current_time = int(time.time())
    if current_time - auth_date > ttl:
        raise AuthenticationError("اعتبار داده‌های تلگرام منقضی شده است (Replay Check).")

    # 3. Construct data_check_string (alphabetically sorted by key, joined with \n)
    sorted_items = sorted(parsed_data.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)

    # 4. Generate Secret Key & Verification HMAC
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logger.warning(f"HMAC validation failed for initData. Received: {received_hash[:8]}..., Computed: {computed_hash[:8]}...")
        raise AuthenticationError("امضای دیجیتال تلگرام نامعتبر است.")

    # 5. Extract User Payload
    user_json = parsed_data.get("user")
    if not user_json:
        raise AuthenticationError("اطلاعات کاربر در initData موجود نیست.")

    try:
        user_dict = json.loads(unquote(user_json))
        telegram_user = TelegramUser(**user_dict)
    except Exception as e:
        raise AuthenticationError(f"خطا در خواندن اطلاعات کاربر تلگرام: {e}")

    role = "ADMIN" if telegram_user.id in settings.SUPER_ADMIN_IDS else "USER"

    return AuthenticatedUser(
        id=telegram_user.id,
        first_name=telegram_user.first_name,
        username=telegram_user.username,
        photo_url=telegram_user.photo_url,
        role=role,
        is_mock=False
    )
