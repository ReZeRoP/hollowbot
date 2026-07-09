"""
Entrypoint: build the Bot + Dispatcher, wire middlewares, routers, scheduler,
seed default settings, and start long-polling.

Run:  python bot.py
(Docker runs `alembic upgrade head && python bot.py`.)
"""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.db.base import SessionFactory
from app.handlers import build_root_router
from app.logger import get_logger, setup_logging
from app.middlewares.db_session import DBSessionMiddleware
from app.middlewares.force_join import ForceJoinMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.scheduler.jobs import setup_scheduler
from app.services import settings_service

log = get_logger(__name__)


async def on_startup(bot: Bot) -> None:
    async with SessionFactory() as db:
        await settings_service.seed_defaults(db)
    log.info("Startup complete. Default settings seeded.")


async def main() -> None:
    setup_logging()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # --- middlewares (order: throttle -> db/user -> force-join) ---
    dp.update.outer_middleware(ThrottlingMiddleware(rate_limit=0.4))
    dp.update.outer_middleware(DBSessionMiddleware())
    dp.message.middleware(ForceJoinMiddleware())
    dp.callback_query.middleware(ForceJoinMiddleware())

    # --- routers ---
    dp.include_router(build_root_router())

    # --- scheduler ---
    scheduler = setup_scheduler(bot)
    scheduler.start()

    await on_startup(bot)

    log.info("Bot is up. Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")
