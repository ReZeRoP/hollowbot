"""
Receipt intake: user sends a receipt photo while in TopUpStates.receipt or
PurchaseStates.receipt. We store a pending Payment and forward it to the admin
group with approve/reject buttons.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PaymentPurpose, User
from app.keyboards.admin_kb import approval_kb
from app.logger import get_logger
from app.services import payment_service
from app.states.fsm import PurchaseStates, TopUpStates
from app.utils.texts import MSG

router = Router(name="payment")
log = get_logger(__name__)


async def _handle_receipt(message: Message, state: FSMContext, db: AsyncSession,
                          user: User, purpose: PaymentPurpose):
    data = await state.get_data()
    amount = int(data.get("amount", 0))
    plan_id = data.get("plan_id")
    file_id = message.photo[-1].file_id

    payment = await payment_service.create_pending(
        db, user=user, amount=amount, purpose=purpose,
        receipt_file_id=file_id, plan_id=plan_id,
    )
    await state.clear()
    await message.answer(MSG["receipt_received"])

    # Forward to admin group for approval
    if settings.admin_group_id:
        caption = (
            f"🧾 <b>درخواست پرداخت #{payment.id}</b>\n"
            f"کاربر: <a href='tg://user?id={user.telegram_id}'>{user.full_name}</a>"
            f" (@{user.username or '-'})\n"
            f"شناسه: <code>{user.telegram_id}</code>\n"
            f"نوع: {'شارژ کیف پول' if purpose == PaymentPurpose.WALLET_TOPUP else 'خرید پلن'}\n"
            f"مبلغ: <b>{amount:,} {settings.currency}</b>"
        )
        try:
            sent = await message.bot.send_photo(
                settings.admin_group_id, file_id, caption=caption,
                parse_mode="HTML", reply_markup=approval_kb(payment.id),
            )
            payment.admin_message_id = sent.message_id
            await db.commit()
        except Exception as e:  # noqa: BLE001
            log.error("failed to post receipt to admin group: %s", e)


@router.message(TopUpStates.receipt, F.photo)
async def topup_receipt(message: Message, state: FSMContext, db: AsyncSession, user: User):
    await _handle_receipt(message, state, db, user, PaymentPurpose.WALLET_TOPUP)


@router.message(PurchaseStates.receipt, F.photo)
async def purchase_receipt(message: Message, state: FSMContext, db: AsyncSession, user: User):
    await _handle_receipt(message, state, db, user, PaymentPurpose.PLAN_PURCHASE)


@router.message(TopUpStates.receipt)
@router.message(PurchaseStates.receipt)
async def receipt_needs_photo(message: Message):
    await message.answer("لطفاً عکس رسید را ارسال کن. 📷")
