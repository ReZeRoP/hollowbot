# Architecture

## Overview
A modular, async Telegram bot (aiogram v3) that sells & manages VPN configs by
driving one or more **3X-UI (Sanaei)** panels through their HTTP API.

```
Telegram  ──►  aiogram Dispatcher
                    │
        ┌───────────┼──────────────────────────┐
        │           │                           │
   Middlewares   Routers (handlers)        APScheduler jobs
   (throttle,    (start, buy, wallet,      (sync usage, alerts,
    db+user,      payment, free, refer,     health, backup,
    force-join)   user_panel, admin)        monthly reset)
        │           │                           │
        └───────────┼───────────────────────────┘
                    ▼
                Services (business logic)
   user / plan / panel / subscription / payment / wallet /
   referral / free_config / settings
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   SQLAlchemy (async)      3X-UI Panel client
   SQLite / PostgreSQL     (login, addClient, updateClient,
   + Alembic migrations     delClient, resetTraffic, getTraffics)
                                │
                                ▼
                        sub_builder (VLESS / VMess /
                        Trojan / SS + subscription link)
```

## Layered design
- **handlers/** — thin Telegram I/O; parse input, call services, render replies.
- **services/** — all business rules; the only layer allowed to touch DB + panel.
- **panel/** — 3X-UI HTTP client + link/config builders (no DB knowledge).
- **db/** — engine, session, ORM models.
- **middlewares/** — cross-cutting: DB session injection, user resolution,
  throttling, force-join.
- **keyboards/**, **utils/**, **states/** — presentation, helpers, FSM.
- **scheduler/** — periodic background jobs.

## Folder structure
```
vpn_bot/
├─ bot.py                     # entrypoint (Dispatcher, middlewares, polling)
├─ scripts_seed.py            # optional demo seeding
├─ alembic.ini
├─ requirements.txt
├─ Dockerfile / docker-compose.yml
├─ .env.example
├─ migrations/                # Alembic (async env.py)
├─ docs/                      # this documentation
└─ app/
   ├─ config.py               # typed settings from .env
   ├─ logger.py
   ├─ db/
   │  ├─ base.py              # async engine + session factory
   │  └─ models.py            # ALL tables
   ├─ panel/
   │  ├─ xui_client.py        # 3X-UI API client (auth, retries)
   │  ├─ sub_builder.py       # build sub links + per-protocol URIs
   │  └─ exceptions.py
   ├─ services/
   │  ├─ user_service.py
   │  ├─ plan_service.py
   │  ├─ panel_service.py     # multi-panel selection + inbound sync
   │  ├─ subscription_service.py   # provision/renew/sync/delete on panel
   │  ├─ payment_service.py   # card-to-card approve/reject, wallet buy
   │  ├─ wallet_service.py    # ledger
   │  ├─ referral_service.py  # invites + rewards
   │  ├─ free_config_service.py    # monthly free + anti-fraud
   │  └─ settings_service.py  # runtime-editable settings
   ├─ handlers/
   │  ├─ start.py  free_config.py  referral.py  buy.py  wallet.py
   │  ├─ payment.py  user_panel.py  support.py  tutorials.py
   │  └─ admin/ (admin_menu.py, approvals.py, filters.py)
   ├─ keyboards/ (user_kb.py, admin_kb.py)
   ├─ middlewares/ (db_session.py, force_join.py, throttling.py)
   ├─ states/fsm.py
   ├─ scheduler/jobs.py
   └─ utils/ (texts.py, formatting.py, qrcode_util.py, security.py)
```

## Multi-server / multi-panel
`Panel` rows hold each 3X-UI instance's URL/creds + public connect host.
`panel_service.pick_panel()` does weighted random selection across healthy
panels; `sync_inbounds()` caches inbounds so `Plan` rows can map to specific
inbound(s). A subscription remembers which panel it lives on.

## Why aiogram v3
Native asyncio, first-class FSM, router/middleware architecture, and clean
dependency injection via middleware `data` — ideal for this modular design.
Alternative worth considering at very large scale: aiogram + Redis FSM storage
and Celery instead of APScheduler for distributed workers.
