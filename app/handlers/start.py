"""/start, referral capture, main menu, rules, and the force-join recheck."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards.user_kb import main_menu
from app.services import referral_service, user_service
from app.utils.texts import BTN, MSG

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def start_with_ref(message: Message, command: CommandObject, db: AsyncSession, user: User):
    """Handle t.me/Bot?start=ref_<id> deep links."""
    payload = (command.args or "").strip()
    if payload.startswith("ref_"):
        inviter = await user_service.get_by_referral_code(db, payload)
        if inviter:
            await referral_service.register_referral(db, inviter, user)
    await _send_welcome(message, user)


@router.message(CommandStart())
async def start_plain(message: Message, user: User):
    await _send_welcome(message, user)


async def _send_welcome(message: Message, user: User):
    if user.is_banned:
        await message.answer(MSG["banned"])
        return
    await message.answer(
        MSG["welcome"].format(name=user.full_name or "دوست"),
        reply_markup=main_menu(is_admin=user.is_admin()),
    )


@router.callback_query(F.data == "check_join")
async def recheck_join(cb: CallbackQuery, user: User):
    # ForceJoinMiddleware already verified membership if we got here.
    await cb.message.answer(
        MSG["welcome"].format(name=user.full_name or "دوست"),
        reply_markup=main_menu(is_admin=user.is_admin()),
    )
    await cb.answer()


@router.message(F.text == BTN["rules"])
async def rules(message: Message):
    await message.answer(MSG["rules"])


@router.callback_query(F.data == "cancel")
async def cancel_cb(cb: CallbackQuery):
    await cb.message.edit_text(MSG["cancelled"])
    await cb.answer()
