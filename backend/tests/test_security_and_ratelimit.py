import pytest
from app.core.security import verify_telegram_init_data, AuthenticatedUser
from app.core.access_control import AccessControl
from app.core.rate_limiter import RateLimiter
from app.core.exceptions import RateLimitExceeded, UserBannedError


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
