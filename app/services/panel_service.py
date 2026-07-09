"""
Panel selection + inbound sync helpers.

`pick_panel()` implements naive weighted load-balancing across healthy panels.
`sync_inbounds()` refreshes the cached `inbounds` rows from a live panel.
`client_for()` builds a configured XUIClient for a Panel row.
"""
from __future__ import annotations

import json
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Inbound, Panel
from app.panel.xui_client import XUIClient


def client_for(panel: Panel) -> XUIClient:
    return XUIClient(panel.base_url, panel.username, panel.password)


async def list_panels(db: AsyncSession, only_active: bool = True) -> list[Panel]:
    stmt = select(Panel)
    if only_active:
        stmt = stmt.where(Panel.is_active.is_(True), Panel.is_healthy.is_(True))
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def pick_panel(db: AsyncSession) -> Panel | None:
    """Weighted random pick among active + healthy panels."""
    panels = await list_panels(db, only_active=True)
    if not panels:
        return None
    weighted = []
    for p in panels:
        weighted.extend([p] * max(1, p.weight))
    return random.choice(weighted)


async def sync_inbounds(db: AsyncSession, panel: Panel) -> int:
    """Pull inbounds from the live panel and upsert cached rows. Returns count."""
    async with client_for(panel) as client:
        inbounds = await client.list_inbounds()

    count = 0
    for ib in inbounds:
        pid = ib.get("id")
        res = await db.execute(
            select(Inbound).where(
                Inbound.panel_id == panel.id, Inbound.inbound_id == pid
            )
        )
        row = res.scalar_one_or_none()
        stream = ib.get("streamSettings")
        stream = stream if isinstance(stream, str) else json.dumps(stream or {})
        if row:
            row.remark = ib.get("remark")
            row.protocol = ib.get("protocol")
            row.port = ib.get("port")
            row.stream_settings = stream
        else:
            db.add(
                Inbound(
                    panel_id=panel.id,
                    inbound_id=pid,
                    remark=ib.get("remark"),
                    protocol=ib.get("protocol"),
                    port=ib.get("port"),
                    stream_settings=stream,
                )
            )
        count += 1
    await db.commit()
    return count
