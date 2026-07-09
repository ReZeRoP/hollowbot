"""
Payment approval callbacks handled in the admin group.

Approve -> credit wallet / provision plan, notify the user with the sub link.
Reject  -> mark rejected, notify the user.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Payment, PaymentPurpose, User
from app.logger import get_logger
from app.services import payment_service
from app.utils.texts import MSG

router = Router(name="approvals")
log = get_logger(__name__)


def _is_admin_actor(user: User) -> bool:
    return bool(user and user.is_admin())


@router.callback_query(F.data.startswith("pay_ok:"))
async def approve(cb: CallbackQuery, db: AsyncSession, user: User):
    if not _is_admin_actor(user):
        await cb.answer(MSG["not_admin"], show_alert=True)
        return
    payment_id = int(cb.data.split(":")[1])
    payment = await db.get(Payment, payment_id)
    if not payment:
        await cb.answer("یافت نشد", show_alert=True)
        return

    try:
        result = await payment_service.approve(db, payment, cb.from_user.id)
    except Exception as e:  # noqa: BLE001
        log.exception("approve failed: %s", e)
        await cb.answer("خطا در پردازش", show_alert=True)
        return

    target = await db.get(User, payment.user_id)

    # Notify the buyer
    try:
        if result["kind"] == PaymentPurpose.WALLET_TOPUP.value:
            await cb.bot.send_message(
                target.telegram_id,
                f"✅ شارژ کیف پول شما به مبلغ {payment.amount:,} {settings.currency} تأیید شد.",
            )
        elif result["kind"] == PaymentPurpose.PLAN_PURCHASE.value and "subscription" in result:
            sub = result["subscription"]
            await cb.bot.send_message(
                target.telegram_id,
                MSG["purchase_ok"].format(link=sub.sub_link),
                parse_mode="HTML",
            )
    except Exception as e:  # noqa: BLE001
        log.warning("notify buyer failed: %s", e)

    await cb.message.edit_caption(
        caption=(cb.message.caption or "") + f"\n\n✅ تأیید شد توسط {cb.from_user.full_name}",
        reply_markup=None,
    )
    await cb.answer("تأیید شد")


@router.callback_query(F.data.startswith("pay_no:"))
async def reject(cb: CallbackQuery, db: AsyncSession, user: User):
    if not _is_admin_actor(user):
        await cb.answer(MSG["not_admin"], show_alert=True)
        return
    payment_id = int(cb.data.split(":")[1])
    payment = await db.get(Payment, payment_id)
    if not payment:
        await cb.answer("یافت نشد", show_alert=True)
        return

    await payment_service.reject(db, payment, cb.from_user.id, note="rejected by admin")
    target = await db.get(User, payment.user_id)
    try:
        await cb.bot.send_message(
            target.telegram_id,
            "❌ متأسفانه رسید پرداخت شما تأیید نشد. برای پیگیری با پشتیبانی در تماس باش.",
        )
    except Exception:  # noqa: BLE001
        pass
    await cb.message.edit_caption(
        caption=(cb.message.caption or "") + f"\n\n❌ رد شد توسط {cb.from_user.full_name}",
        reply_markup=None,
    )
    await cb.answer("رد شد")
