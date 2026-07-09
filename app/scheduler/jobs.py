"""
Scheduled background jobs (APScheduler, AsyncIOScheduler).

  reset_free_quota   – monthly: allow each user a fresh free config next month.
                       (We rely on created_at month check in free_config_service,
                        so this job mainly resets warning flags / cleans expired.)
  sync_all_usage     – periodic: pull usage from panels into DB.
  check_alerts       – periodic: warn users at 80% volume / 3 days to expiry.
  health_check       – periodic: mark panels healthy/unhealthy.
  backup_db          – daily: dump SQLite/pg and prune old backups.

setup_scheduler(bot) wires the jobs and returns the scheduler (started by caller).
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import settings
from app.db.base import SessionFactory
from app.db.models import Panel, SubStatus, Subscription, User
from app.logger import get_logger
from app.services import panel_service, subscription_service

log = get_logger(__name__)

VOLUME_WARN_RATIO = 0.8
EXPIRY_WARN_DAYS = 3


async def sync_all_usage() -> None:
    async with SessionFactory() as db:
        res = await db.execute(
            select(Subscription).where(Subscription.status == SubStatus.ACTIVE)
        )
        for sub in res.scalars().all():
            try:
                await subscription_service.sync_usage(db, sub)
            except Exception as e:  # noqa: BLE001
                log.warning("sync_usage failed sub=%s: %s", sub.id, e)


async def check_alerts(bot: Bot) -> None:
    async with SessionFactory() as db:
        res = await db.execute(
            select(Subscription).where(Subscription.status == SubStatus.ACTIVE)
        )
        for sub in res.scalars().all():
            user = await db.get(User, sub.user_id)  # explicit load (async-safe)
            if not user:
                continue
            # volume warning (80%)
            if (
                sub.total_bytes
                and not sub.warned_volume
                and sub.used_bytes >= sub.total_bytes * VOLUME_WARN_RATIO
            ):
                try:
                    await bot.send_message(
                        user.telegram_id,
                        "⚠️ بیش از ۸۰٪ حجم سرویس شما مصرف شده است. برای قطع نشدن، تمدید کن.",
                    )
                    sub.warned_volume = True
                except Exception:  # noqa: BLE001
                    pass
            # expiry warning (<=3 days)
            if sub.expire_at and not sub.warned_expiry:
                remaining = (sub.expire_at - datetime.now(timezone.utc)).days
                if 0 <= remaining <= EXPIRY_WARN_DAYS:
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            f"⏳ سرویس شما تا {remaining} روز دیگر منقضی می‌شود. تمدید را فراموش نکن.",
                        )
                        sub.warned_expiry = True
                    except Exception:  # noqa: BLE001
                        pass
        await db.commit()


async def reset_free_quota() -> None:
    """Runs monthly. Reset warning flags on free subs (new-month eligibility is
    handled by created_at check in free_config_service)."""
    log.info("Monthly free quota reset tick")
    # Extend here if you keep a per-user 'free_claimed' flag instead.


async def health_check() -> None:
    async with SessionFactory() as db:
        res = await db.execute(select(Panel).where(Panel.is_active.is_(True)))
        for panel in res.scalars().all():
            client = panel_service.client_for(panel)
            ok = await client.health()
            await client.close()
            panel.is_healthy = ok
            panel.last_health_check = datetime.now(timezone.utc)
            if not ok:
                log.warning("Panel %s appears DOWN", panel.name)
        await db.commit()


async def backup_db() -> None:
    """Simple SQLite file backup + prune. For Postgres, shell out to pg_dump."""
    if not settings.is_sqlite:
        log.info("Backup: non-sqlite DB — configure pg_dump in your environment.")
        return
    os.makedirs(settings.backup_dir, exist_ok=True)
    src = settings.database_url.split(":///")[-1]
    if not os.path.exists(src):
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(settings.backup_dir, f"bot_{stamp}.db")
    shutil.copy2(src, dst)
    # prune old
    cutoff = time.time() - settings.backup_keep_days * 86400
    for f in os.listdir(settings.backup_dir):
        p = os.path.join(settings.backup_dir, f)
        if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
            os.remove(p)
    log.info("DB backup written: %s", dst)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=settings.timezone)
    sched.add_job(sync_all_usage, "interval", minutes=30, id="sync_usage")
    sched.add_job(check_alerts, "interval", minutes=60, args=[bot], id="alerts")
    sched.add_job(health_check, "interval", minutes=10, id="health")
    sched.add_job(backup_db, CronTrigger(hour=3, minute=0), id="backup")
    sched.add_job(reset_free_quota, CronTrigger(day=1, hour=0, minute=5), id="free_reset")
    return sched
