"""User lookup / creation, roles, bans."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as env
from app.db.models import User, UserRole
from app.utils.security import gen_referral_code


async def get_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    res = await db.execute(select(User).where(User.telegram_id == telegram_id))
    return res.scalar_one_or_none()


async def get_by_referral_code(db: AsyncSession, code: str) -> User | None:
    res = await db.execute(select(User).where(User.referral_code == code))
    return res.scalar_one_or_none()


async def get_or_create(
    db: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    full_name: str | None,
) -> tuple[User, bool]:
    """Return (user, created)."""
    user = await get_by_telegram_id(db, telegram_id)
    if user:
        # keep profile fresh
        changed = False
        if user.username != username:
            user.username, changed = username, True
        if user.full_name != full_name:
            user.full_name, changed = full_name, True
        if changed:
            await db.commit()
        return user, False

    role = UserRole.SUPER_ADMIN if telegram_id in env.super_admin_ids else UserRole.USER
    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        role=role,
        referral_code=gen_referral_code(telegram_id),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, True


async def set_ban(db: AsyncSession, user: User, banned: bool, reason: str | None = None) -> None:
    user.is_banned = banned
    user.ban_reason = reason
    await db.commit()


async def set_role(db: AsyncSession, user: User, role: UserRole) -> None:
    user.role = role
    await db.commit()


async def count_users(db: AsyncSession) -> int:
    res = await db.execute(select(func.count(User.id)))
    return int(res.scalar() or 0)
