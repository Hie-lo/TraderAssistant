from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.system import SystemSetting, AdminAuditLog
from app.core.logger import logger


class DynamicConfigManager:
    """In-memory cache for dynamic system settings backed by PostgreSQL."""

    _cache: Dict[str, Any] = {}

    @classmethod
    async def load_all(cls, session: AsyncSession) -> None:
        """Loads all dynamic settings from system_settings into RAM cache."""
        result = await session.execute(select(SystemSetting))
        rows = result.scalars().all()
        for row in rows:
            cls._cache[row.key] = row.value_json
        logger.info(f"Loaded {len(cls._cache)} dynamic configuration keys into memory.")

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value from in-memory cache in O(1) time."""
        return cls._cache.get(key, default)

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Returns a copy of all current cached settings."""
        return cls._cache.copy()

    @classmethod
    async def set(cls, session: AsyncSession, key: str, value: Any, admin_id: Optional[int] = None, description: Optional[str] = None) -> None:
        """Persists setting in database, updates RAM cache, and logs to AdminAuditLog."""
        result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()

        old_val = cls._cache.get(key)
        if setting:
            setting.value_json = value
            if description:
                setting.description = description
            if admin_id:
                setting.updated_by = admin_id
        else:
            setting = SystemSetting(
                key=key,
                value_json=value,
                description=description,
                updated_by=admin_id
            )
            session.add(setting)

        # Update in-memory cache immediately
        cls._cache[key] = value

        # Record audit log
        audit = AdminAuditLog(
            admin_id=admin_id or 0,
            action="UPDATE_CONFIG",
            target_id=key,
            details_json={
                "key": key,
                "old_value": old_val,
                "new_value": value
            }
        )
        session.add(audit)
        await session.commit()
        logger.info(f"Dynamic config '{key}' updated by admin {admin_id}: {value}")


# Singleton alias
DynamicConfig = DynamicConfigManager
