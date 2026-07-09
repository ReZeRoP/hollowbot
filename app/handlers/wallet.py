"""Wallet: show balance + start top-up (ask amount -> show card)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.keyboards.user_kb import cancel_kb, wallet_kb
from app.services import settings_service
from app.states.fsm import TopUpStates
from app.utils.texts import BTN, MSG

router = Router(name="wallet")


@router.message(F.text == BTN["wallet"])
async def wallet_panel(message: Message, user: User):
    await message.answer(
        MSG["wallet_info"].format(balance=f"{user.balance:,}", currency=settings.currency),
        reply_markup=wallet_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "topup")
async def topup_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(TopUpStates.amount)
    await cb.message.answer(
        MSG["topup_ask_amount"].format(currency=settings.currency), reply_markup=cancel_kb()
    )
    await cb.answer()


@router.message(TopUpStates.amount, F.text.regexp(r"^\d[\d,]*$"))
async def topup_amount(message: Message, state: FSMContext, db: AsyncSession):
    amount = int(message.text.replace(",", ""))
    if amount < 1000:
        await message.answer("مبلغ باید حداقل ۱۰۰۰ تومان باشد.")
        return
    card = await settings_service.get(db, "card_number")
    holder = await settings_service.get(db, "card_holder")
    await state.update_data(amount=amount)
    await state.set_state(TopUpStates.receipt)
    await message.answer(
        MSG["topup_card"].format(amount=f"{amount:,}", currency=settings.currency,
                                 card=card, holder=holder),
        parse_mode="HTML",
    )
