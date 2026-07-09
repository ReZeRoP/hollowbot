"""Plan CRUD + inbound mapping."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Inbound, Plan


async def list_active(db: AsyncSession) -> list[Plan]:
    res = await db.execute(
        select(Plan)
        .where(Plan.is_active.is_(True))
        .order_by(Plan.sort_order, Plan.price)
        .options(selectinload(Plan.inbounds))
    )
    return list(res.scalars().all())


async def get(db: AsyncSession, plan_id: int) -> Plan | None:
    res = await db.execute(
        select(Plan).where(Plan.id == plan_id).options(selectinload(Plan.inbounds))
    )
    return res.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    title: str,
    volume_gb: float,
    duration_days: int,
    price: int,
    inbound_ids: list[int],
    description: str | None = None,
) -> Plan:
    plan = Plan(
        title=title,
        volume_gb=volume_gb,
        duration_days=duration_days,
        price=price,
        description=description,
    )
    if inbound_ids:
        res = await db.execute(select(Inbound).where(Inbound.id.in_(inbound_ids)))
        plan.inbounds = list(res.scalars().all())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def set_active(db: AsyncSession, plan: Plan, active: bool) -> None:
    plan.is_active = active
    await db.commit()
