"""
Force-join middleware: blocks usage until the user is a member of every
required channel. Allows /start and the 'check_join' callback through so the
user can see the prompt and re-check.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings
from app.keyboards.user_kb import force_join_kb
from app.utils.texts import MSG

_ALLOWED = {"/start", "check_join"}


async def _is_member(bot: Bot, channel: str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status not in ("left", "kicked")
    except Exception:  # noqa: BLE001 — private channel / bot not admin
        return False


class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        channels = settings.force_join_channels
        if not channels:
            return await handler(event, data)

        bot: Bot = data["bot"]
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        # let start / recheck through
        text = getattr(event, "text", None)
        cbdata = getattr(event, "data", None)
        if text in _ALLOWED or cbdata in _ALLOWED:
            # If it's the recheck button, verify membership.
            if cbdata == "check_join":
                joined = all(await _is_member(bot, c, tg_user.id) for c in channels)
                if joined:
                    return await handler(event, data)
                await event.answer(MSG["not_joined"], show_alert=True)
                return
            return await handler(event, data)

        joined = all(await _is_member(bot, c, tg_user.id) for c in channels)
        if joined:
            return await handler(event, data)

        # Not joined -> show prompt, block handler.
        kb = force_join_kb(channels)
        if isinstance(event, Message):
            await event.answer(MSG["force_join"], reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.message.answer(MSG["force_join"], reply_markup=kb)
        return
