from typing import Optional, Any, List
from datetime import datetime
from app.schemas.common import CamelModel


class UpdateUserStatusSchema(CamelModel):
    """Schema for updating a user's status by admin."""
    status: str  # 'ACTIVE', 'RESTRICTED', 'TEMP_BANNED', 'BANNED'
    ban_reason: Optional[str] = None
    duration_minutes: Optional[int] = None  # For TEMP_BANNED


class UpdateConfigSchema(CamelModel):
    """Schema for updating a dynamic configuration parameter."""
    key: str
    value: Any
    description: Optional[str] = None


class AdminUserItemSchema(CamelModel):
    """Admin representation of a user."""
    id: int
    username: Optional[str]
    first_name: str
    role: str
    status: str
    banned_until: Optional[str]
    ban_reason: Optional[str]
    default_balance: str
    trades_count: int
    created_at: str
    last_active_at: str


class ChannelTemplateSchema(CamelModel):
    """Schema for reading/updating the Jinja2 channel post template and target channel."""
    template: str
    channel_id: Optional[str] = None
