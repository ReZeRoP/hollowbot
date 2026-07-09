"""Support ticket: collect a message and forward to the admin group."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Ticket, User
from app.keyboards.user_kb import cancel_kb
from app.states.fsm import SupportStates
from app.utils.texts import BTN, MSG

router = Router(name="support")


@router.message(F.text == BTN["support"])
async def support_start(message: Message, state: FSMContext):
    await state.set_state(SupportStates.message)
    await message.answer(MSG["support_ask"], reply_markup=cancel_kb())


@router.message(SupportStates.message, F.text)
async def support_collect(message: Message, state: FSMContext, db: AsyncSession, user: User):
    ticket = Ticket(user_id=user.id, message=message.text)
    db.add(ticket)
    await db.commit()
    await state.clear()
    await message.answer(MSG["support_sent"])
    if settings.admin_group_id:
        await message.bot.send_message(
            settings.admin_group_id,
            f"🆘 تیکت جدید از <a href='tg://user?id={user.telegram_id}'>{user.full_name}</a>"
            f" (@{user.username or '-'}):\n\n{message.text}",
            parse_mode="HTML",
        )
