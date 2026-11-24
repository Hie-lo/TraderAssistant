from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.security import AuthenticatedUser
from app.core.config import settings
from app.core.dynamic_config import DynamicConfig
from app.database.seed import DEFAULT_SETTINGS
from app.repositories.user_repo import UserRepository
from app.repositories.system_repo import SystemRepository
from app.services.admin_service import AdminService
from app.services.channel_service import ChannelService
from app.schemas.admin_schema import (
    UpdateUserStatusSchema,
    UpdateConfigSchema,
    AdminUserItemSchema,
    ChannelTemplateSchema,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=List[AdminUserItemSchema])
async def list_users(
    limit: int = 50,
    offset: int = 0,
    admin_user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Lists registered users along with trade counts and ban statuses."""
    user_repo = UserRepository(db)
    rows = await user_repo.list_users_with_trade_count(limit=limit, offset=offset)

    return [
        AdminUserItemSchema(
            id=u.id,
            username=u.username,
            first_name=u.first_name,
            role=u.role,
            status=u.status,
            banned_until=u.banned_until.isoformat() if u.banned_until else None,
            ban_reason=u.ban_reason,
            default_balance=f"{u.default_balance:.2f}",
            trades_count=count,
            created_at=u.created_at.strftime("%Y-%m-%d %H:%M"),
            last_active_at=u.last_active_at.strftime("%Y-%m-%d %H:%M")
        )
        for u, count in rows
    ]


@router.post("/users/{target_user_id}/status")
async def update_user_status(
    target_user_id: int,
    payload: UpdateUserStatusSchema,
    admin_user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bans, unbans, or restricts a user."""
    updated = await AdminService.change_user_status(
        session=db,
        admin_id=admin_user.id,
        target_user_id=target_user_id,
        new_status=payload.status,
        ban_reason=payload.ban_reason,
        duration_minutes=payload.duration_minutes
    )
    return {
        "success": True,
        "message": f"وضعیت کاربر {target_user_id} به {updated.status} تغییر یافت."
    }


@router.get("/config")
async def get_dynamic_config(
    admin_user: AuthenticatedUser = Depends(require_admin)
):
    """Returns all current dynamic runtime settings from RAM cache."""
    return DynamicConfig.get_all()


@router.put("/config")
async def update_dynamic_config(
    payload: UpdateConfigSchema,
    admin_user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Updates a dynamic setting in both PostgreSQL and RAM."""
    await AdminService.update_dynamic_config(
        session=db,
        admin_id=admin_user.id,
        key=payload.key,
        value=payload.value,
        description=payload.description
    )
    return {
        "success": True,
        "message": f"تنظیم '{payload.key}' با موفقیت به‌روزرسانی شد."
    }


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = 50,
    admin_user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Returns recent administrative and security audit actions."""
    system_repo = SystemRepository(db)
    logs = await system_repo.list_recent_audit_logs(limit=limit)
    return [
        {
            "id": l.id,
            "admin_id": l.admin_id,
            "action": l.action,
            "target_id": l.target_id,
            "details": l.details_json,
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for l in logs
    ]


@router.get("/template", response_model=ChannelTemplateSchema)
async def get_channel_template(
    admin_user: AuthenticatedUser = Depends(require_admin)
):
    """Returns the current Jinja2 channel post template and configured target channel ID."""
    template_str = DynamicConfig.get(
        "channel_post_template",
        DEFAULT_SETTINGS["channel_post_template"]
    )
    channel_id = DynamicConfig.get("channel_id") or str(settings.CHANNEL_ID or "")
    return ChannelTemplateSchema(template=template_str, channel_id=channel_id)


@router.put("/template")
async def update_channel_template(
    payload: ChannelTemplateSchema,
    admin_user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Validates and updates the Jinja2 channel post template (and optional channel_id)."""
    ChannelService.validate_template(payload.template)

    await AdminService.update_dynamic_config(
        session=db,
        admin_id=admin_user.id,
        key="channel_post_template",
        value=payload.template,
        description="Jinja2 template for Telegram channel trade posts"
    )
    if payload.channel_id is not None:
        await AdminService.update_dynamic_config(
            session=db,
            admin_id=admin_user.id,
            key="channel_id",
            value=payload.channel_id.strip(),
            description="Target Telegram channel ID/username for trade publishing"
        )

    return {
        "success": True,
        "template": payload.template,
        "channelId": DynamicConfig.get("channel_id") or str(settings.CHANNEL_ID or "")
    }
