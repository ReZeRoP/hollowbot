"""
Referral logic:

  • register_referral()  – on first /start with ?start=ref_<id>, bind invitee to
    inviter and grant the inviter bonus GB (added to `bonus_gb`, on top of the
    free monthly quota).
  • reward_topup()       – when an invitee tops up, pay the inviter a % of the
    top-up as wallet credit (paid BY THE SYSTEM, invitee balance untouched).
  • stats()              – counts / gb / revenue for the referral panel.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Referral, TxType, User
from app.services import settings_service, wallet_service


async def register_referral(db: AsyncSession, inviter: User, invitee: User) -> bool:
    """Bind invitee->inviter once. Returns True if a new referral was created."""
    if inviter.id == invitee.id:
        return False
    if invitee.referred_by_id is not None:
        return False  # already referred by someone

    existing = await db.execute(
        select(Referral).where(Referral.invitee_id == invitee.id)
    )
    if existing.scalar_one_or_none():
        return False

    bonus_gb = await settings_service.get_float(db, "referral_bonus_gb")
    invitee.referred_by_id = inviter.id
    inviter.bonus_gb += bonus_gb

    db.add(Referral(inviter_id=inviter.id, invitee_id=invitee.id, bonus_gb_granted=bonus_gb))
    await db.commit()
    return True


async def reward_topup(db: AsyncSession, invitee: User, topup_amount: int) -> int:
    """
    Pay inviter `percent`% of invitee's top-up. Returns reward paid (Toman).
    The invitee's balance is NOT touched — the system funds the reward.
    """
    if not invitee.referred_by_id:
        return 0

    percent = await settings_service.get_float(db, "referral_topup_percent")
    reward = int(topup_amount * percent / 100)
    if reward <= 0:
        return 0

    inviter = await db.get(User, invitee.referred_by_id)
    if not inviter:
        return 0

    await wallet_service.record(
        db,
        inviter,
        tx_type=TxType.REFERRAL_REWARD,
        amount=reward,
        description=f"پاداش دعوت از کاربر {invitee.telegram_id}",
        commit=False,
    )

    res = await db.execute(
        select(Referral).where(
            Referral.inviter_id == inviter.id, Referral.invitee_id == invitee.id
        )
    )
    ref = res.scalar_one_or_none()
    if ref:
        ref.revenue_earned += reward
    await db.commit()
    return reward


async def stats(db: AsyncSession, user: User) -> dict:
    count = await db.execute(
        select(func.count(Referral.id)).where(Referral.inviter_id == user.id)
    )
    revenue = await db.execute(
        select(func.coalesce(func.sum(Referral.revenue_earned), 0)).where(
            Referral.inviter_id == user.id
        )
    )
    return {
        "count": int(count.scalar() or 0),
        "bonus_gb": user.bonus_gb,
        "revenue": int(revenue.scalar() or 0),
    }
