"""Connection tutorials section."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.utils.texts import BTN, TUTORIALS

router = Router(name="tutorials")


@router.message(F.text == BTN["tutorials"])
async def tutorials(message: Message):
    # Extend with photos/videos via message.answer_photo / answer_video.
    await message.answer(TUTORIALS)
