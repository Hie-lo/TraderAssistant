from typing import Optional, Any, Dict


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str = "Internal application error", status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(AppException):
    """Raised when Telegram authentication or token validation fails."""

    def __init__(self, message: str = "احراز هویت تلگرام نامعتبر است", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=401, details=details)


class AuthorizationError(AppException):
    """Raised when user lacks required privileges."""

    def __init__(self, message: str = "دسترسی به این بخش مجاز نمی‌باشد", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=403, details=details)


class UserBannedError(AppException):
    """Raised when a banned or restricted user tries to execute a forbidden action."""

    def __init__(self, message: str = "حساب کاربری شما مسدود یا محدود شده است", ban_reason: Optional[str] = None, banned_until: Optional[str] = None):
        details = {
            "ban_reason": ban_reason or "نقض قوانین سیستم",
            "banned_until": banned_until
        }
        super().__init__(message=message, status_code=403, details=details)


class RateLimitExceeded(AppException):
    """Raised when user exceeds API or heavy operations rate limits."""

    def __init__(self, message: str = "تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً کمی صبر کنید.", retry_after: int = 60):
        super().__init__(message=message, status_code=429, details={"retry_after": retry_after})


class NotFoundError(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "مورد درخواستی یافت نشد", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=404, details=details)


class BusinessValidationError(AppException):
    """Raised when financial, mathematical or operational validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=400, details=details)


class MaintenanceModeActive(AppException):
    """Raised when system is in maintenance mode and user is not an admin."""

    def __init__(self, message: str = "سیستم در حال حاضر در حال تعمیر و به‌روزرسانی است. لطفاً بعداً تلاش فرمایید."):
        super().__init__(message=message, status_code=503)
