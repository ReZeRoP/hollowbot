"""
Convenience seeding script (run once after migrations) to create a demo panel
and a couple of plans so you can test end-to-end.

Usage:
    python scripts_seed.py
Edit the PANEL_* values to point at your live 3X-UI panel first.
"""
from __future__ import annotations

import asyncio

from app.db.base import SessionFactory
from app.db.models import Panel
from app.services import panel_service, plan_service, settings_service

# --- EDIT THESE to your live panel ---
PANEL = dict(
    name="Server-1",
    base_url="https://your-panel-host:2053/yourpath",
    username="admin",
    password="admin",
    public_host="your-connect-host.com",
    sub_enabled=False,          # True if you enabled the Subscription Server
    sub_base_url=None,          # e.g. "https://your-host:2096/sub"
)


async def main() -> None:
    async with SessionFactory() as db:
        await settings_service.seed_defaults(db)

        panel = Panel(**PANEL)
        db.add(panel)
        await db.commit()
        await db.refresh(panel)
        print(f"Created panel #{panel.id}")

        # Pull inbounds so plans can map to them.
        try:
            n = await panel_service.sync_inbounds(db, panel)
            print(f"Synced {n} inbounds")
        except Exception as e:  # noqa: BLE001
            print(f"Inbound sync skipped (panel unreachable?): {e}")

        # Example plans (map inbound_ids after you see them in DB).
        await plan_service.create(
            db, title="۱ ماهه ۳۰ گیگ", volume_gb=30, duration_days=30,
            price=120000, inbound_ids=[], description="مناسب استفاده روزمره",
        )
        await plan_service.create(
            db, title="۳ ماهه ۱۰۰ گیگ", volume_gb=100, duration_days=90,
            price=300000, inbound_ids=[], description="اقتصادی",
        )
        print("Created demo plans.")


if __name__ == "__main__":
    asyncio.run(main())
