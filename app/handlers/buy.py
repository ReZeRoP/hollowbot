"""Purchase flow: list plans, buy from wallet, or start card-to-card."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PaymentPurpose, User
from app.keyboards.user_kb import plan_actions_kb, plans_kb
from app.logger import get_logger
from app.services import plan_service, settings_service, payment_service
from app.states.fsm import PurchaseStates
from app.utils.texts import BTN, MSG

router = Router(name="buy")
log = get_logger(__name__)


@router.message(F.text == BTN["buy"])
async def show_plans(message: Message, db: AsyncSession):
    if not await settings_service.get_bool(db, "sales_enabled"):
        await message.answer(MSG["sales_off"])
        return
    plans = await plan_service.list_active(db)
    if not plans:
        await message.answer("فعلاً پلنی برای فروش تعریف نشده است.")
        return
    await message.answer(MSG["choose_plan"], reply_markup=plans_kb(plans))


@router.callback_query(F.data.startswith("plan:"))
async def plan_detail(cb: CallbackQuery, db: AsyncSession):
    plan_id = int(cb.data.split(":")[1])
    plan = await plan_service.get(db, plan_id)
    if not plan:
        await cb.answer("پلن یافت نشد", show_alert=True)
        return
    text = MSG["plan_detail"].format(
        title=plan.title, gb=plan.volume_gb, days=plan.duration_days,
        price=f"{plan.price:,}", currency=settings.currency, desc=plan.description or "",
    )
    await cb.message.edit_text(text, reply_markup=plan_actions_kb(plan.id), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "back_plans")
async def back_plans(cb: CallbackQuery, db: AsyncSession):
    plans = await plan_service.list_active(db)
    await cb.message.edit_text(MSG["choose_plan"], reply_markup=plans_kb(plans))
    await cb.answer()


@router.callback_query(F.data.startswith("buy_wallet:"))
async def buy_wallet(cb: CallbackQuery, db: AsyncSession, user: User):
    plan_id = int(cb.data.split(":")[1])
    plan = await plan_service.get(db, plan_id)
    if not plan:
        await cb.answer("پلن یافت نشد", show_alert=True)
        return
    try:
        sub = await payment_service.purchase_with_wallet(db, user, plan)
    except ValueError:
        await cb.answer()
        await cb.message.answer(MSG["insufficient_balance"])
        return
    except Exception as e:  # noqa: BLE001
        log.exception("wallet purchase failed: %s", e)
        await cb.message.answer(MSG["error"])
        return
    await cb.message.answer(MSG["purchase_ok"].format(link=sub.sub_link), parse_mode="HTML")
    await cb.answer("✅ خرید انجام شد")


@router.callback_query(F.data.startswith("buy_card:"))
async def buy_card(cb: CallbackQuery, state: FSMContext, db: AsyncSession):
    plan_id = int(cb.data.split(":")[1])
    plan = await plan_service.get(db, plan_id)
    if not plan:
        await cb.answer("پلن یافت نشد", show_alert=True)
        return
    card = await settings_service.get(db, "card_number")
    holder = await settings_service.get(db, "card_holder")
    await state.set_state(PurchaseStates.receipt)
    await state.update_data(plan_id=plan.id, amount=plan.price)
    await cb.message.answer(
        MSG["topup_card"].format(amount=f"{plan.price:,}", currency=settings.currency,
                                 card=card, holder=holder),
        parse_mode="HTML",
    )
    await cb.answer()
