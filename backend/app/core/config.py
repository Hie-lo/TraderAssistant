from typing import List, Union
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Infrastructure server configuration read from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENV_MODE: str = "development"
    BOT_TOKEN: str = "7000000000:AAExampleTelegramBotTokenPlaceholder"
    ADMIN_LOG_CHANNEL_ID: Union[int, str] = -1001234567890
    CHANNEL_ID: Union[int, str] = ""
    SUPER_ADMIN_IDS: List[int] = [111111111]
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_db"
    MINI_APP_URL: str = "https://localhost:5173"
    STORAGE_DIR: str = "storage"
    LOGS_DIR: str = "logs"

    @field_validator(
        "ENV_MODE",
        "BOT_TOKEN",
        "ADMIN_LOG_CHANNEL_ID",
        "CHANNEL_ID",
        "DATABASE_URL",
        "MINI_APP_URL",
        "STORAGE_DIR",
        "LOGS_DIR",
        mode="before",
    )
    @classmethod
    def strip_env_strings(cls, v):
        if isinstance(v, str):
            return v.strip().replace("\r", "").replace("\n", "")
        return v

    @field_validator("SUPER_ADMIN_IDS", mode="before")
    @classmethod
    def parse_super_admin_ids(cls, v: Union[str, List[int], int]) -> List[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    return [int(x) for x in parsed]
                except Exception:
                    pass
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        return []


settings = Settings()
