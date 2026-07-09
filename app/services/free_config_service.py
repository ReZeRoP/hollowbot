"""
Free monthly config logic + abuse prevention.

Rules:
  • Each Telegram account gets ONE free config per calendar month.
  • Volume = free_quota_gb + the user's earned referral bonus_gb.
  • Period = free_period_days.
  • Anti-fraud: refuse brand-new account with no username (looks_suspicious).

Monthly reset is handled by the scheduler (jobs.reset_free_quota).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SubKind, Subscription, User
from app.services import settings_service, subscription_service
from app.utils.security import account_age_days, looks_suspicious


async def _current_month_free_sub(db: AsyncSession, user: User) -> Subscription | None:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    res = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.kind == SubKind.FREE,
            Subscription.created_at >= month_start,
        )
    )
    return res.scalar_one_or_none()


async def eligibility(db: AsyncSession, user: User) -> tuple[bool, str]:
    """Return (ok, reason_key)."""
    if user.is_banned:
        return False, "banned"
    if looks_suspicious(
        username=user.username, account_age_days=account_age_days(user.joined_at)
    ):
        return False, "suspicious"
    if await _current_month_free_sub(db, user):
        return False, "already"
    return True, "ok"


async def claim(db: AsyncSession, user: User) -> Subscription:
    """Provision the free monthly config. Caller must check eligibility() first."""
    quota = await settings_service.get_float(db, "free_quota_gb")
    days = await settings_service.get_int(db, "free_period_days")
    volume = quota + (user.bonus_gb or 0.0)  # referral bonus stacks on top
    return await subscription_service.provision(
        db,
        user=user,
        volume_gb=volume,
        duration_days=days,
        kind=SubKind.FREE,
        tag="free",
    )
