"""Reusable admin-only filter."""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.db.models import User


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, user: User) -> bool:
        return bool(user and user.is_admin())
