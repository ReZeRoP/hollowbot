"""'My configs' panel: list subscriptions, show usage, QR, individual configs, renew."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SubStatus, User
from app.keyboards.user_kb import sub_actions_kb
from app.logger import get_logger
from app.services import subscription_service
from app.utils.formatting import fmt_date, human_bytes
from app.utils.qrcode_util import make_qr_png
from app.utils.texts import BTN, MSG

router = Router(name="user_panel")
log = get_logger(__name__)

_STATUS_FA = {
    SubStatus.ACTIVE: "🟢 فعال",
    SubStatus.EXPIRED: "🔴 منقضی",
    SubStatus.DISABLED: "⚫️ غیرفعال",
    SubStatus.PENDING: "🟡 در انتظار",
}


@router.message(F.text == BTN["my_configs"])
async def my_configs(message: Message, db: AsyncSession, user: User):
    subs = await subscription_service.get_user_subscriptions(db, user)
    if not subs:
        await message.answer(MSG["no_configs"])
        return
    for sub in subs:
        # refresh usage from panel (best-effort)
        try:
            await subscription_service.sync_usage(db, sub)
        except Exception as e:  # noqa: BLE001
            log.warning("sync_usage failed for sub %s: %s", sub.id, e)
        title = sub.plan.title if sub.plan else ("رایگان" if sub.kind.value == "free" else "کانفیگ")
        total = "نامحدود" if sub.total_bytes == 0 else human_bytes(sub.total_bytes)
        await message.answer(
            MSG["config_card"].format(
                title=title, status=_STATUS_FA.get(sub.status, "-"),
                used=human_bytes(sub.used_bytes), total=total,
                expire=fmt_date(sub.expire_at), link=sub.sub_link or "-",
            ),
            reply_markup=sub_actions_kb(sub.id),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("qr:"))
async def show_qr(cb: CallbackQuery, db: AsyncSession):
    sub_id = int(cb.data.split(":")[1])
    from app.db.models import Subscription
    sub = await db.get(Subscription, sub_id)
    if not sub or not sub.sub_link:
        await cb.answer("لینکی موجود نیست", show_alert=True)
        return
    png = make_qr_png(sub.sub_link)
    await cb.message.answer_photo(
        BufferedInputFile(png.read(), filename="config_qr.png"),
        caption="📷 برای اتصال، این QR را در اپلیکیشن اسکن کن.",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cfgs:"))
async def get_individual_configs(cb: CallbackQuery, db: AsyncSession):
    sub_id = int(cb.data.split(":")[1])
    from app.db.models import Panel, Subscription
    sub = await db.get(Subscription, sub_id)
    if not sub:
        await cb.answer("یافت نشد", show_alert=True)
        return
    panel = await db.get(Panel, sub.panel_id)
    from app.services.subscription_service import _resolve_inbounds, build_configs
    inbounds = await _resolve_inbounds(db, sub.plan, panel)
    try:
        configs = await build_configs(db, sub, panel, inbounds)
    except Exception as e:  # noqa: BLE001
        log.warning("build_configs failed: %s", e)
        configs = []
    if not configs:
        await cb.answer("کانفیگی ساخته نشد", show_alert=True)
        return
    body = "\n\n".join(f"<code>{c}</code>" for c in configs)
    await cb.message.answer(f"📥 کانفیگ‌های تکی:\n\n{body}", parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data.startswith("renew:"))
async def renew_prompt(cb: CallbackQuery, db: AsyncSession):
    # For brevity: renewing routes the user to the plans menu.
    await cb.answer()
    await cb.message.answer("برای تمدید، یک پلن را از منوی «🛒 خرید کانفیگ» انتخاب کن.")
