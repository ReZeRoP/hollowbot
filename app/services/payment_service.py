"""
Card-to-card payment lifecycle.

  create_pending()  – user submitted a receipt; store Payment(PENDING).
  approve()         – admin approved: credit wallet (top-up) OR provision plan
                      (purchase), fire referral top-up reward, mark APPROVED.
  reject()          – admin rejected: mark REJECTED with a reason.

Approval side-effects are transactional-ish: we commit at the end.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Payment,
    PaymentPurpose,
    PaymentStatus,
    Plan,
    SubKind,
    TxType,
    User,
)
from app.services import (
    plan_service,
    referral_service,
    subscription_service,
    wallet_service,
)


async def create_pending(
    db: AsyncSession,
    *,
    user: User,
    amount: int,
    purpose: PaymentPurpose,
    receipt_file_id: str,
    plan_id: int | None = None,
) -> Payment:
    payment = Payment(
        user_id=user.id,
        amount=amount,
        purpose=purpose,
        plan_id=plan_id,
        receipt_file_id=receipt_file_id,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def approve(db: AsyncSession, payment: Payment, admin_tg_id: int) -> dict:
    """
    Apply the payment. Returns a result dict describing what happened so the
    handler can notify the user (e.g. {'kind': 'topup'} or {'kind':'purchase',
    'subscription': <Subscription>}).
    """
    if payment.status != PaymentStatus.PENDING:
        return {"kind": "noop", "reason": "already_reviewed"}

    user = await db.get(User, payment.user_id)
    result: dict = {"kind": payment.purpose.value}

    if payment.purpose == PaymentPurpose.WALLET_TOPUP:
        await wallet_service.record(
            db, user, tx_type=TxType.TOPUP, amount=payment.amount,
            description="شارژ کیف پول (کارت‌به‌کارت)", ref_payment_id=payment.id,
            commit=False,
        )
        # Pay referral reward (system-funded) to inviter, if any.
        reward = await referral_service.reward_topup(db, user, payment.amount)
        result["referral_reward"] = reward

    elif payment.purpose == PaymentPurpose.PLAN_PURCHASE:
        plan: Plan | None = await plan_service.get(db, payment.plan_id)
        if plan is None:
            payment.status = PaymentStatus.REJECTED
            payment.review_note = "plan_not_found"
            await db.commit()
            return {"kind": "noop", "reason": "plan_not_found"}
        sub = await subscription_service.provision(
            db, user=user, volume_gb=plan.volume_gb, duration_days=plan.duration_days,
            kind=SubKind.PAID, plan=plan, tag=f"p{plan.id}",
        )
        result["subscription"] = sub

    payment.status = PaymentStatus.APPROVED
    payment.reviewed_by = admin_tg_id
    payment.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return result


async def reject(db: AsyncSession, payment: Payment, admin_tg_id: int, note: str | None) -> None:
    if payment.status != PaymentStatus.PENDING:
        return
    payment.status = PaymentStatus.REJECTED
    payment.reviewed_by = admin_tg_id
    payment.review_note = note
    payment.reviewed_at = datetime.now(timezone.utc)
    await db.commit()


async def purchase_with_wallet(db: AsyncSession, user: User, plan: Plan):
    """Buy a plan directly from wallet balance (no receipt needed)."""
    if user.balance < plan.price:
        raise ValueError("insufficient_balance")
    await wallet_service.record(
        db, user, tx_type=TxType.PURCHASE, amount=-plan.price,
        description=f"خرید پلن {plan.title}", commit=False,
    )
    sub = await subscription_service.provision(
        db, user=user, volume_gb=plan.volume_gb, duration_days=plan.duration_days,
        kind=SubKind.PAID, plan=plan, tag=f"p{plan.id}",
    )
    await db.commit()
    return sub
