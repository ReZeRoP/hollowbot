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
from app.logger import get_logger
from app.utils.texts import MSG

log = get_logger(__name__)

_ALLOWED = {"/start", "check_join"}


async def _is_member(bot: Bot, channel: str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status not in ("left", "kicked")
    except Exception as e:  # noqa: BLE001
        # Log the REAL reason instead of silently treating it as "not joined".
        # Common causes:
        #  - the bot itself is not an admin of the channel (most common)
        #  - channel value in .env is not "@username" (e.g. a t.me/ link, or
        #    missing the leading @)
        #  - channel is private and needs the numeric chat id, not @username
        log.warning(
            "force_join: get_chat_member(%r, user_id=%s) failed: %s",
            channel, user_id, e,
        )
        return False


async def _all_joined(bot: Bot, channels: list[str], user_id: int) -> bool:
    """
    Check membership in every channel, short-circuiting on the first miss.

    NOTE: do NOT write this as `all(await _is_member(...) for c in channels)`.
    A generator expression containing `await`, evaluated inside an async
    function, is compiled as an ASYNC generator (per PEP 530) — and `all()`
    cannot consume an async generator, raising:
        TypeError: 'async_generator' object is not iterable
    Awaiting each check explicitly in a real loop avoids that entirely.
    """
    for channel in channels:
        if not await _is_member(bot, channel, user_id):
            return False
    return True


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
                joined = await _all_joined(bot, channels, tg_user.id)
                if joined:
                    return await handler(event, data)
                await event.answer(MSG["not_joined"], show_alert=True)
                return
            return await handler(event, data)

        joined = await _all_joined(bot, channels, tg_user.id)
        if joined:
            return await handler(event, data)

        # Not joined -> show prompt, block handler.
        kb = force_join_kb(channels)
        if isinstance(event, Message):
            await event.answer(MSG["force_join"], reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.message.answer(MSG["force_join"], reply_markup=kb)
        return
