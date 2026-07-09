"""
Admin menu: stats, settings toggles, broadcast.

Advanced management (plans/panels/users CRUD) is stubbed with clear TODOs so
the structure is complete and easy to extend.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment, PaymentStatus, Subscription, SubStatus, User
from app.handlers.admin.filters import IsAdmin
from app.keyboards.admin_kb import admin_menu, settings_kb
from app.services import settings_service, user_service
from app.states.fsm import AdminStates
from app.utils.texts import BTN, MSG

router = Router(name="admin_menu")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == BTN["admin"])
async def open_admin(message: Message):
    await message.answer("⚙️ پنل مدیریت:", reply_markup=admin_menu())


@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery, db: AsyncSession):
    users = await user_service.count_users(db)
    active_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubStatus.ACTIVE)
    )
    revenue = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.APPROVED
        )
    )
    await cb.message.edit_text(
        f"📊 <b>آمار</b>\n\n"
        f"👥 کاربران: <b>{users}</b>\n"
        f"🟢 سرویس‌های فعال: <b>{int(active_subs.scalar() or 0)}</b>\n"
        f"💰 مجموع درآمد تأییدشده: <b>{int(revenue.scalar() or 0):,}</b>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "adm:settings")
async def open_settings(cb: CallbackQuery):
    await cb.message.edit_text("⚙️ تنظیمات:", reply_markup=settings_kb())
    await cb.answer()


@router.callback_query(F.data == "set:toggle_sales")
async def toggle_sales(cb: CallbackQuery, db: AsyncSession):
    current = await settings_service.get_bool(db, "sales_enabled")
    await settings_service.set(db, "sales_enabled", "false" if current else "true")
    await cb.answer(f"فروش {'خاموش' if current else 'روشن'} شد", show_alert=True)


@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcast)
    await cb.message.answer("📢 متن پیام همگانی را ارسال کن:")
    await cb.answer()


@router.message(AdminStates.broadcast, F.text)
async def broadcast_send(message: Message, state: FSMContext, db: AsyncSession):
    await state.clear()
    res = await db.execute(select(User.telegram_id).where(User.is_banned.is_(False)))
    ids = [r[0] for r in res.all()]
    sent = failed = 0
    for tid in ids:
        try:
            await message.bot.send_message(tid, message.text)
            sent += 1
        except Exception:  # noqa: BLE001
            failed += 1
    await message.answer(f"✅ ارسال شد: {sent} | ❌ ناموفق: {failed}")


# --- Stubs for future full CRUD (kept minimal & documented) -----------------
@router.callback_query(F.data.in_({"adm:plans", "adm:panels", "adm:users"}))
async def not_yet(cb: CallbackQuery):
    # TODO: implement full CRUD screens for plans / panels / users.
    await cb.answer("این بخش در حال توسعه است. مدیریت از طریق سرویس‌ها/دیتابیس ممکن است.", show_alert=True)
