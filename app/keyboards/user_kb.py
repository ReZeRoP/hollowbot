"""User-facing keyboards (reply main menu + inline sub-menus)."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.utils.texts import BTN


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN["buy"]), KeyboardButton(text=BTN["free"])],
        [KeyboardButton(text=BTN["my_configs"]), KeyboardButton(text=BTN["wallet"])],
        [KeyboardButton(text=BTN["referral"]), KeyboardButton(text=BTN["tutorials"])],
        [KeyboardButton(text=BTN["support"]), KeyboardButton(text=BTN["rules"])],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=BTN["admin"])])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def force_join_kb(channels: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        uname = ch.lstrip("@")
        rows.append([InlineKeyboardButton(text=f"📢 {ch}", url=f"https://t.me/{uname}")])
    rows.append([InlineKeyboardButton(text=BTN["check_join"], callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plans_kb(plans) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{p.title} — {p.price:,}", callback_data=f"plan:{p.id}")]
        for p in plans
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_actions_kb(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت با کیف پول", callback_data=f"buy_wallet:{plan_id}")],
        [InlineKeyboardButton(text="🧾 کارت‌به‌کارت", callback_data=f"buy_card:{plan_id}")],
        [InlineKeyboardButton(text=BTN["back"], callback_data="back_plans")],
    ])


def sub_actions_kb(sub_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=BTN["qr"], callback_data=f"qr:{sub_id}"),
            InlineKeyboardButton(text=BTN["get_configs"], callback_data=f"cfgs:{sub_id}"),
        ],
        [InlineKeyboardButton(text=BTN["renew"], callback_data=f"renew:{sub_id}")],
    ])


def wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN["topup"], callback_data="topup")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN["cancel"], callback_data="cancel")],
    ])
