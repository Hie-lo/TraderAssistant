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
    subscription_end_date: Optional[str] = None
    created_at: str
    last_active_at: str


class ChannelTemplateSchema(CamelModel):
    """Schema for reading/updating the Jinja2 channel post template and target channel."""
    template: str
    channel_id: Optional[str] = None


class ManualVipEditSchema(CamelModel):
    """Schema for admin manual VIP day/date/role edits."""
    action: str  # 'add_days', 'sub_days', 'set_date', 'revoke', 'set_role'
    days: Optional[int] = None
    exact_date: Optional[str] = None
    role: Optional[str] = None


class VipSettingsUpdateSchema(CamelModel):
    """Schema for admin updates to bank card details and VIP plan prices."""
    admin_card_number: str
    admin_card_name: str
    vip_prices: Any
