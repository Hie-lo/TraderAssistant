import hmac
import hashlib
import json
import time
from urllib.parse import urlencode
import pytest
from app.core.config import Settings, settings
from app.core.dynamic_config import DynamicConfig
from app.core.security import verify_telegram_init_data, AuthenticatedUser
from app.core.access_control import AccessControl
from app.core.rate_limiter import RateLimiter
from app.core.exceptions import AuthenticationError, RateLimitExceeded, UserBannedError


def test_dev_mode_mock_user():
    """In development mode, verify_telegram_init_data returns mock user for empty/DEV_MOCK_USER."""
    user = verify_telegram_init_data(None)
    assert user.id == 111111111
    assert user.first_name == "امیرحسین"
    assert user.is_mock is True

    user2 = verify_telegram_init_data("DEV_MOCK_USER")
    assert user2.id == 111111111


def test_access_control_banned_user():
    """Test that a banned user is rejected immediately in memory."""
    AccessControl.set_user_restriction(user_id=99999, status="BANNED", ban_reason="Test Ban")

    with pytest.raises(UserBannedError, match="Test Ban"):
        AccessControl.check_access(user_id=99999, is_heavy_or_write=False)

    # Clean up
    AccessControl.set_user_restriction(user_id=99999, status="ACTIVE")
    # Now allowed
    AccessControl.check_access(user_id=99999)


def test_rate_limiter_burst_auto_ban():
    """Test auto-shield triggers temp ban when burst exceeds threshold."""
    user_id = 88888
    # Clear any previous requests
    RateLimiter._general_requests.pop(user_id, None)

    with pytest.raises(RateLimitExceeded, match="ضد اسپم"):
        for _ in range(55):
            RateLimiter.check_rate_limit(user_id=user_id)

    # Check that user is placed in TEMP_BANNED in memory
    status = AccessControl.get_user_status(user_id)
    assert status is not None
    assert status.status == "TEMP_BANNED"

    # Clean up
    AccessControl.set_user_restriction(user_id, "ACTIVE")


def test_settings_strips_whitespace_and_crlf():
    """Config parsing must strip trailing spaces and CR/LF from DATABASE_URL and env strings."""
    cfg = Settings(
        DATABASE_URL=" postgresql+asyncpg://u:p@db:5432/trading_db\r\n ",
        BOT_TOKEN=" 7000000000:AAFakeToken\r ",
        MINI_APP_URL="https://nini.biscuitandpeanut.online\r\n",
    )
    assert cfg.DATABASE_URL == "postgresql+asyncpg://u:p@db:5432/trading_db"
    assert cfg.BOT_TOKEN == "7000000000:AAFakeToken"
    assert cfg.MINI_APP_URL == "https://nini.biscuitandpeanut.online"


def _build_signed_init_data(bot_token: str, auth_date: int, user_id: int = 777777) -> str:
    fields = {
        "auth_date": str(auth_date),
        "user": json.dumps({"id": user_id, "first_name": "Tester", "username": "tester"}, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_init_data_enforces_strict_one_hour_ttl(monkeypatch):
    """Telegram initData older than 3600s must fail even if dynamic TTL was set higher."""
    monkeypatch.setattr(settings, "ENV_MODE", "production")
    monkeypatch.setattr(DynamicConfig, "_cache", {**DynamicConfig._cache, "telegram_init_data_ttl_sec": 7200})

    now = int(time.time())
    fresh_init_data = _build_signed_init_data(settings.BOT_TOKEN, now - 60)
    verified = verify_telegram_init_data(fresh_init_data)
    assert verified.id == 777777

    expired_init_data = _build_signed_init_data(settings.BOT_TOKEN, now - 3605)
    with pytest.raises(AuthenticationError):
        verify_telegram_init_data(expired_init_data)
