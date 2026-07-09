"""Admin keyboards."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 آمار", callback_data="adm:stats"),
         InlineKeyboardButton(text="📢 پیام همگانی", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="📦 پلن‌ها", callback_data="adm:plans"),
         InlineKeyboardButton(text="🖥 سرورها/پنل‌ها", callback_data="adm:panels")],
        [InlineKeyboardButton(text="👥 کاربران", callback_data="adm:users"),
         InlineKeyboardButton(text="⚙️ تنظیمات", callback_data="adm:settings")],
    ])


def approval_kb(payment_id: int) -> InlineKeyboardMarkup:
    """Approve/reject buttons attached to a receipt posted in the admin group."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تأیید", callback_data=f"pay_ok:{payment_id}"),
            InlineKeyboardButton(text="❌ رد", callback_data=f"pay_no:{payment_id}"),
        ]
    ])


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 حجم رایگان", callback_data="set:free_quota_gb")],
        [InlineKeyboardButton(text="🤝 درصد پاداش دعوت", callback_data="set:referral_topup_percent")],
        [InlineKeyboardButton(text="🛑 روشن/خاموش فروش", callback_data="set:toggle_sales")],
    ])
