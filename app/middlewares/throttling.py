"""
Simple in-memory rate limiter (per user) to prevent spam / flooding.

For multi-process deployments swap the dict for Redis. Good enough for a
single-process aiogram bot.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.5) -> None:
        self.rate_limit = rate_limit
        self._last: dict[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is not None:
            now = time.monotonic()
            if now - self._last[tg_user.id] < self.rate_limit:
                return  # silently drop flood
            self._last[tg_user.id] = now
        return await handler(event, data)
