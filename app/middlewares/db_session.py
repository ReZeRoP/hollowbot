"""
Injects a fresh AsyncSession into every handler as `data['db']`, and also
resolves/creates the current `data['user']` (User row) for convenience.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.db.base import SessionFactory
from app.services import user_service


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with SessionFactory() as session:
            data["db"] = session
            tg_user = data.get("event_from_user")
            if tg_user is not None:
                user, _ = await user_service.get_or_create(
                    session,
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    full_name=tg_user.full_name,
                )
                data["user"] = user
            return await handler(event, data)
