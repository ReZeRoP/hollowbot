"""Small security/anti-fraud helpers."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone


def gen_referral_code(telegram_id: int) -> str:
    """Deterministic-ish but unguessable referral code."""
    return f"ref_{telegram_id}"


def gen_client_email(telegram_id: int, tag: str = "") -> str:
    """
    Unique, panel-safe client identifier ("email" field on 3X-UI).
    Example: tg123456789-free-a1b2  /  tg123456789-p12-9f3c
    """
    suffix = secrets.token_hex(2)
    tag = tag or "cfg"
    return f"tg{telegram_id}-{tag}-{suffix}"


def gen_sub_id() -> str:
    return secrets.token_urlsafe(9)


def account_age_days(joined_at: datetime) -> int:
    return (datetime.now(timezone.utc) - joined_at).days


def looks_suspicious(*, username: str | None, account_age_days: int) -> bool:
    """
    Very lightweight fraud heuristic for the free-config gate:
    no username + brand-new account => flag for stricter checks.
    Tune / extend as needed.
    """
    return username is None and account_age_days < 1
