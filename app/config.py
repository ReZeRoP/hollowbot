"""
Central configuration loaded from environment (.env).

Uses pydantic-settings so every value is typed and validated on startup.
Runtime-editable settings (free quota, referral %, sales on/off) are also
mirrored in the `settings` DB table; `.env` provides the initial defaults
(see app/services/settings_service.py).
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    bot_token: str = Field(alias="BOT_TOKEN")
    super_admin_ids: List[int] = Field(default_factory=list, alias="SUPER_ADMIN_IDS")
    admin_group_id: int | None = Field(default=None, alias="ADMIN_GROUP_ID")
    force_join_channels: List[str] = Field(default_factory=list, alias="FORCE_JOIN_CHANNELS")

    # --- Database ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/bot.db", alias="DATABASE_URL"
    )

    # --- Locale ---
    currency: str = Field(default="تومان", alias="CURRENCY")
    locale: str = Field(default="fa", alias="LOCALE")
    timezone: str = Field(default="Asia/Tehran", alias="TIMEZONE")

    # --- Free config defaults ---
    free_quota_gb: float = Field(default=5, alias="FREE_QUOTA_GB")
    free_period_days: int = Field(default=30, alias="FREE_PERIOD_DAYS")

    # --- Referral defaults ---
    referral_bonus_gb: float = Field(default=1, alias="REFERRAL_BONUS_GB")
    referral_topup_percent: float = Field(default=10, alias="REFERRAL_TOPUP_PERCENT")

    # --- Payments ---
    card_number: str = Field(default="", alias="CARD_NUMBER")
    card_holder: str = Field(default="", alias="CARD_HOLDER")

    # --- Flags ---
    sales_enabled: bool = Field(default=True, alias="SALES_ENABLED")

    # --- Backups ---
    backup_dir: str = Field(default="./backups", alias="BACKUP_DIR")
    backup_keep_days: int = Field(default=14, alias="BACKUP_KEEP_DAYS")

    # --- Logging ---
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---- validators: allow comma-separated strings from .env ----
    @field_validator("super_admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

    @field_validator("force_join_channels", mode="before")
    @classmethod
    def _parse_channels(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so the .env is parsed only once per process."""
    return Settings()


settings = get_settings()
