"""Aggregate every router into a single one registered on the Dispatcher."""
from aiogram import Router

from app.handlers import (
    buy,
    free_config,
    payment,
    referral,
    start,
    support,
    tutorials,
    user_panel,
    wallet,
)
from app.handlers.admin import admin_menu, approvals


def build_root_router() -> Router:
    root = Router(name="root")
    # order matters: start first, admin approval callbacks early
    root.include_router(start.router)
    root.include_router(approvals.router)
    root.include_router(admin_menu.router)
    root.include_router(free_config.router)
    root.include_router(referral.router)
    root.include_router(buy.router)
    root.include_router(wallet.router)
    root.include_router(payment.router)
    root.include_router(user_panel.router)
    root.include_router(support.router)
    root.include_router(tutorials.router)
    return root
