"""Free monthly config handler."""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.logger import get_logger
from app.panel.exceptions import PanelError
from app.services import free_config_service, settings_service
from app.utils.formatting import bytes_to_gb
from app.utils.texts import BTN, MSG

router = Router(name="free_config")
log = get_logger(__name__)

_REASON_MSG = {
    "banned": MSG["banned"],
    "suspicious": "برای دریافت کانفیگ رایگان، حساب تلگرام شما باید یوزرنیم داشته و قدیمی‌تر باشد.",
}


@router.message(F.text == BTN["free"])
async def free_config(message: Message, db: AsyncSession, user: User):
    ok, reason = await free_config_service.eligibility(db, user)
    if not ok:
        if reason == "already":
            now = datetime.now(timezone.utc)
            nxt = (now.replace(day=1) if now.month == 12 else now.replace(month=now.month + 1, day=1))
            await message.answer(MSG["free_already"].format(reset=nxt.strftime("%Y-%m-%d")))
        else:
            await message.answer(_REASON_MSG.get(reason, MSG["error"]))
        return

    wait = await message.answer("⏳ در حال ساخت کانفیگ رایگان...")
    try:
        sub = await free_config_service.claim(db, user)
    except PanelError as e:
        log.error("free config panel error: %s", e)
        await wait.edit_text(MSG["error"])
        return
    except Exception as e:  # noqa: BLE001
        log.exception("free config failed: %s", e)
        await wait.edit_text(MSG["error"])
        return

    days = await settings_service.get_int(db, "free_period_days")
    await wait.edit_text(
        MSG["free_created"].format(
            gb=bytes_to_gb(sub.total_bytes), days=days, link=sub.sub_link
        ),
        parse_mode="HTML",
    )
