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

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    bot_token: str = Field(alias="BOT_TOKEN")
    # NOTE: these two are read as plain strings (NOT List[...]) on purpose.
    # pydantic-settings tries to JSON-decode env vars typed as list/dict
    # BEFORE any custom validator runs, so a plain comma-separated value like
    # "111111111,222222222" or "@my_channel" would crash with a
    # SettingsError ("Expecting value..."). Keeping them as `str` here and
    # exposing parsed List[...] via read-only properties below sidesteps
    # that entirely.
    super_admin_ids_str: str = Field(default="", alias="SUPER_ADMIN_IDS")
    admin_group_id: int | None = Field(default=None, alias="ADMIN_GROUP_ID")
    force_join_channels_str: str = Field(default="", alias="FORCE_JOIN_CHANNELS")

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

    # ---- parsed accessors (comma-separated -> list) ----
    @property
    def super_admin_ids(self) -> List[int]:
        return [int(x.strip()) for x in self.super_admin_ids_str.split(",") if x.strip()]

    @property
    def force_join_channels(self) -> List[str]:
        return [x.strip() for x in self.force_join_channels_str.split(",") if x.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so the .env is parsed only once per process."""
    return Settings()


settings = get_settings()
