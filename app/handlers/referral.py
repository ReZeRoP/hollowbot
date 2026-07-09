"""Referral panel: show link + stats."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.services import referral_service, settings_service
from app.utils.texts import BTN, MSG

router = Router(name="referral")


@router.message(F.text == BTN["referral"])
async def referral_panel(message: Message, db: AsyncSession, user: User):
    bot_username = (await message.bot.me()).username
    link = f"https://t.me/{bot_username}?start={user.referral_code}"
    stats = await referral_service.stats(db, user)
    bonus = await settings_service.get_float(db, "referral_bonus_gb")
    percent = await settings_service.get_float(db, "referral_topup_percent")
    await message.answer(
        MSG["referral_info"].format(
            link=link,
            bonus=bonus,
            percent=int(percent),
            count=stats["count"],
            gb=stats["bonus_gb"],
            revenue=f"{stats['revenue']:,}",
            currency=settings.currency,
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
