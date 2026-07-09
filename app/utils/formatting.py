"""Formatting helpers: bytes<->GB, dates, money, status labels."""
from __future__ import annotations

from datetime import datetime, timezone

GB = 1024**3


def gb_to_bytes(gb: float) -> int:
    return int(gb * GB)


def bytes_to_gb(b: int) -> float:
    return round(b / GB, 2)


def human_bytes(b: int) -> str:
    if b <= 0:
        return "نامحدود" if b == 0 else "0"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def fmt_money(amount: int) -> str:
    """Group thousands: 150000 -> '150,000'."""
    return f"{amount:,}"


def days_to_expiry_ms(days: int) -> int:
    """Return an epoch-millis expiry `days` from now (0 => 0 = never)."""
    if days <= 0:
        return 0
    ts = datetime.now(timezone.utc).timestamp() + days * 86400
    return int(ts * 1000)


def ms_to_datetime(ms: int) -> datetime | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def fmt_date(dt: datetime | None) -> str:
    if not dt:
        return "نامحدود"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")
