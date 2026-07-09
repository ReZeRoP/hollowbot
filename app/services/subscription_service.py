"""
Subscription (config) provisioning — ties the DB to the 3X-UI panel.

  provision()      – create a client on the panel's inbound(s) and persist a
                     Subscription row + built subscription link.
  build_links()    – (re)build the sub link + individual config URIs.
  sync_usage()     – pull up/down/expiry from panel into our DB.
  renew()          – extend volume/time on an existing subscription.
  reset_traffic()  – zero usage (used by free monthly reset).
  delete()         – remove client from panel + mark row disabled.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Inbound,
    Panel,
    Plan,
    SubKind,
    SubStatus,
    Subscription,
    User,
)
from app.logger import get_logger
from app.panel import sub_builder
from app.services import panel_service
from app.utils.formatting import days_to_expiry_ms, gb_to_bytes
from app.utils.security import gen_client_email, gen_sub_id

log = get_logger(__name__)


async def _resolve_inbounds(db: AsyncSession, plan: Plan | None, panel: Panel) -> list[Inbound]:
    """Which inbounds to place the client on. Plan-mapped or all panel inbounds."""
    if plan and plan.inbounds:
        return [ib for ib in plan.inbounds if ib.panel_id == panel.id] or plan.inbounds
    res = await db.execute(
        select(Inbound).where(Inbound.panel_id == panel.id, Inbound.is_active.is_(True))
    )
    return list(res.scalars().all())


async def provision(
    db: AsyncSession,
    *,
    user: User,
    volume_gb: float,
    duration_days: int,
    kind: SubKind,
    plan: Plan | None = None,
    panel: Panel | None = None,
    tag: str = "cfg",
) -> Subscription:
    """
    Create a client on the panel and return a persisted, active Subscription.
    Raises PanelError subclasses on failure (handled by caller).
    """
    panel = panel or await panel_service.pick_panel(db)
    if panel is None:
        raise RuntimeError("no_available_panel")

    inbounds = await _resolve_inbounds(db, plan, panel)
    if not inbounds:
        raise RuntimeError("no_inbounds_configured")

    email = gen_client_email(user.telegram_id, tag)
    sub_id = gen_sub_id()
    expiry_ms = days_to_expiry_ms(duration_days)
    client_uuid = None

    async with panel_service.client_for(panel) as client:
        # Add the same client identity to each mapped inbound.
        for ib in inbounds:
            client_uuid = await client.add_client(
                ib.inbound_id,
                email=email,
                client_uuid=client_uuid,   # reuse uuid across inbounds
                total_gb=volume_gb,
                expiry_ts_ms=expiry_ms,
                sub_id=sub_id,
            )

    sub = Subscription(
        user_id=user.id,
        panel_id=panel.id,
        plan_id=plan.id if plan else None,
        kind=kind,
        status=SubStatus.ACTIVE,
        client_uuid=client_uuid,
        client_email=email,
        sub_id=sub_id,
        total_bytes=gb_to_bytes(volume_gb),
        expire_at=None,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    sub.sub_link = await _primary_link(db, sub, panel, inbounds)
    await db.commit()
    log.info("Provisioned %s sub for user %s on panel %s", kind.value, user.telegram_id, panel.name)
    return sub


async def _primary_link(db: AsyncSession, sub: Subscription, panel: Panel, inbounds: list[Inbound]) -> str:
    """Subscription-server link if enabled, else self-hosted base64 of configs."""
    if panel.sub_enabled and panel.sub_base_url:
        return sub_builder.build_subscription_link(panel.sub_base_url, sub.sub_id)
    configs = await build_configs(db, sub, panel, inbounds)
    return "data:sub;base64," + sub_builder.build_selfhosted_subscription(configs)


async def build_configs(
    db: AsyncSession, sub: Subscription, panel: Panel, inbounds: list[Inbound]
) -> list[str]:
    """Build individual VLESS/VMess/Trojan/SS URIs for every inbound."""
    configs: list[str] = []
    for ib in inbounds:
        raw = {
            "protocol": ib.protocol,
            "port": ib.port,
            "streamSettings": ib.stream_settings,
            "settings": json.dumps({"clients": [{"id": sub.client_uuid, "flow": ""}]}),
        }
        configs += sub_builder.build_configs_for_inbound(
            host=panel.public_host,
            inbound=raw,
            client_uuid=sub.client_uuid,
            client_password=sub.client_uuid,   # trojan/ss use password == uuid here
            remark=f"{panel.name}-{sub.client_email}",
        )
    return configs


async def get_user_subscriptions(db: AsyncSession, user: User) -> list[Subscription]:
    res = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.status != SubStatus.DISABLED)
        .options(selectinload(Subscription.plan), selectinload(Subscription.panel))
        .order_by(Subscription.created_at.desc())
    )
    return list(res.scalars().all())


async def sync_usage(db: AsyncSession, sub: Subscription) -> None:
    """Pull live up/down/expiry from the panel into the DB row."""
    panel = await db.get(Panel, sub.panel_id)
    if not panel:
        return
    async with panel_service.client_for(panel) as client:
        traffic = await client.get_client_traffic(sub.client_email)
    if not traffic:
        return
    sub.up_bytes = traffic.get("up", 0)
    sub.down_bytes = traffic.get("down", 0)
    sub.total_bytes = traffic.get("total", sub.total_bytes)
    enable = traffic.get("enable", True)
    if not enable:
        sub.status = SubStatus.DISABLED
    await db.commit()


async def renew(db: AsyncSession, sub: Subscription, *, add_gb: float, add_days: int) -> None:
    """Extend an existing subscription's volume/time on the panel."""
    panel = await db.get(Panel, sub.panel_id)
    inbounds = await _resolve_inbounds(db, sub.plan, panel)
    new_total_gb = (sub.total_bytes / 1024**3) + add_gb
    expiry_ms = days_to_expiry_ms(add_days) if add_days else 0
    async with panel_service.client_for(panel) as client:
        for ib in inbounds:
            await client.update_client(
                ib.inbound_id,
                sub.client_uuid,
                email=sub.client_email,
                total_gb=new_total_gb,
                expiry_ts_ms=expiry_ms,
                sub_id=sub.sub_id,
            )
    sub.total_bytes = gb_to_bytes(new_total_gb)
    sub.status = SubStatus.ACTIVE
    sub.warned_volume = False
    sub.warned_expiry = False
    await db.commit()


async def reset_traffic(db: AsyncSession, sub: Subscription) -> None:
    panel = await db.get(Panel, sub.panel_id)
    inbounds = await _resolve_inbounds(db, sub.plan, panel)
    async with panel_service.client_for(panel) as client:
        for ib in inbounds:
            await client.reset_client_traffic(ib.inbound_id, sub.client_email)
    sub.up_bytes = sub.down_bytes = 0
    sub.status = SubStatus.ACTIVE
    sub.warned_volume = False
    await db.commit()


async def delete(db: AsyncSession, sub: Subscription) -> None:
    panel = await db.get(Panel, sub.panel_id)
    inbounds = await _resolve_inbounds(db, sub.plan, panel)
    async with panel_service.client_for(panel) as client:
        for ib in inbounds:
            try:
                await client.delete_client(ib.inbound_id, sub.client_uuid)
            except Exception as e:  # noqa: BLE001
                log.warning("delete_client failed: %s", e)
    sub.status = SubStatus.DISABLED
    await db.commit()
