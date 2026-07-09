"""
Runtime-editable settings backed by the `settings` table.

On first run we seed defaults from .env (app.config.settings). Admins can then
change them live (free quota, referral %, sales on/off) without redeploying.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as env
from app.db.models import Setting

DEFAULTS: dict[str, str] = {
    "free_quota_gb": str(env.free_quota_gb),
    "free_period_days": str(env.free_period_days),
    "referral_bonus_gb": str(env.referral_bonus_gb),
    "referral_topup_percent": str(env.referral_topup_percent),
    "sales_enabled": "true" if env.sales_enabled else "false",
    "card_number": env.card_number,
    "card_holder": env.card_holder,
}


async def seed_defaults(db: AsyncSession) -> None:
    for key, value in DEFAULTS.items():
        exists = await db.get(Setting, key)
        if not exists:
            db.add(Setting(key=key, value=value))
    await db.commit()


async def get(db: AsyncSession, key: str, default: str | None = None) -> str | None:
    row = await db.get(Setting, key)
    if row:
        return row.value
    return DEFAULTS.get(key, default)


async def get_float(db: AsyncSession, key: str) -> float:
    return float(await get(db, key, "0") or 0)


async def get_int(db: AsyncSession, key: str) -> int:
    return int(float(await get(db, key, "0") or 0))


async def get_bool(db: AsyncSession, key: str) -> bool:
    return (await get(db, key, "false") or "false").lower() == "true"


async def set(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    await db.commit()
