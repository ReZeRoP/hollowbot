# 🤖 HollowBot — VPN Sales & Management Bot (3X-UI / Sanaei)

A professional, modular Telegram bot (aiogram v3, async) that **sells and manages
VPN configs** by driving one or more **3X-UI (Sanaei) panels** via their API —
fully automatic client creation, subscription links, free monthly configs,
referrals, card-to-card payments with admin approval, wallet, and a scheduler.

> UI language: **Persian**. Code & comments: **English**. Currency: **Toman**.
> Default DB: **SQLite** (switch to PostgreSQL via `DATABASE_URL`).

## ⚡ One-command install

Run this on your server (Linux/macOS, Python 3.11+ and git required):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ReZeRoP/hollowbot/main/install.sh)
```

This clones the repo, creates an **isolated** virtual environment, installs
dependencies, creates `.env` from `.env.example`, and runs the database
migrations. It will NOT start the bot — edit `.env` with your real
`BOT_TOKEN` / admin IDs / card info first, then:

```bash
cd hollowbot
source .venv/bin/activate
python bot.py
```

Re-running the same command later pulls the latest changes and re-installs
dependencies (safe to re-run any time).

---

## ✨ Features
- **3X-UI integration**: login/session, retries, add/update/delete client, reset
  traffic, read usage; multi-server load-balancing + inbound sync.
- **Config delivery**: subscription link (panel Sub Server *or* self-hosted
  base64) + individual **VLESS / VMess / Trojan / Shadowsocks** URIs + **QR**.
- **Free monthly config** (5 GB / 30 days, adjustable) with anti-fraud gate.
- **Referrals**: unique link, +1 GB per invite, +10% of invitee top-ups
  (system-funded), live stats.
- **Paid sales**: buy from **wallet** or **card-to-card** with receipt → admin
  **approve/reject** → auto-provision & deliver.
- **Wallet** with full transaction ledger.
- **User panel**: usage, expiry, status, copy link, QR, renew, individual configs.
- **Admin**: stats, broadcast, live settings (free quota, referral %, sales on/off),
  role-based access (user / reseller / admin / super_admin). Plans/panels/users
  CRUD are scaffolded with clear extension points.
- **Force-join**, **rate-limiting**, **tutorials**, **support tickets**.
- **Scheduler**: usage sync, 80%/3-day alerts, panel health checks, DB backups,
  monthly free reset.

See `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/FLOWS.md`.

---

## 🚀 Manual quick start (local, SQLite)

> ⚠️ **Always install into a dedicated virtual environment.** This bot pins
> `pydantic<2.10` (required by `aiogram`). If you `pip install` directly into
> a shared/global Python environment that already has other tools (e.g. `mcp`,
> which needs `pydantic>=2.11`), you'll get unresolvable dependency conflicts
> that have nothing to do with this project. An isolated venv avoids that
> entirely — nothing else installed on your machine matters once you're
> inside `.venv`.

```bash
# 1) Create an ISOLATED environment just for this bot (Python 3.11 or 3.12)
python3 -m venv .venv

# 2) Activate it
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate          # Windows (cmd/PowerShell)

# 3) Confirm you're inside it (should print a path ending in .venv/bin/pip)
which pip

# 4) Install — SQLite-only, no C compiler needed
pip install -r requirements.txt

# 5) Configure
cp .env.example .env
#   → set BOT_TOKEN, SUPER_ADMIN_IDS, ADMIN_GROUP_ID, FORCE_JOIN_CHANNELS,
#     CARD_NUMBER/HOLDER. Keep DATABASE_URL as SQLite for now.
mkdir -p data backups

# 6) Create the schema
alembic revision --autogenerate -m "init"
alembic upgrade head

# 7) (optional) seed a demo panel + plans — edit PANEL_* first
python scripts_seed.py

# 8) Run
python bot.py
```

### Switching to PostgreSQL
Only needed for production/multi-instance setups. Install the extra driver,
then point `DATABASE_URL` at your Postgres instance:
```bash
pip install -r requirements-postgres.txt
# .env: DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```
`asyncpg` ships prebuilt wheels for common Python/OS combos, so this normally
installs instantly. If pip still tries to *build* it from source and fails
(`Failed building wheel for asyncpg`), it means there's no prebuilt wheel for
your exact Python version/OS/architecture. Fixes:
- Use Python 3.12 or 3.11 (broadest wheel coverage) instead of a brand-new
  Python release that may not have wheels yet.
- Or install build tools so it can compile: `sudo apt install build-essential`
  (Debian/Ubuntu) — a C compiler is all asyncpg needs, no extra DB headers.
- Or just stick with SQLite for now — everything in this bot works on either.

## 🐳 Run with Docker

```bash
cp .env.example .env      # fill values
docker compose up -d --build
docker compose logs -f bot
```
`Dockerfile` runs `alembic upgrade head` then `python bot.py` automatically.
The `data/` and `backups/` folders are mounted for persistence.
> Using SQLite? You can delete the `db` service (and `depends_on`) from
> `docker-compose.yml`. For PostgreSQL, set
> `DATABASE_URL=postgresql+asyncpg://vpnbot:vpnbot@db:5432/vpnbot`.

---

## ⚙️ Connecting your 3X-UI panel
Add a `Panel` row (via `scripts_seed.py` or admin/DB) with:
- `base_url` — full panel URL **including path**, e.g.
  `https://host:2053/secretpath`
- `username` / `password` — panel login
- `public_host` — the host clients actually connect to
- `sub_enabled` + `sub_base_url` — if you enabled the panel's Subscription Server
  (e.g. `https://host:2096/sub`); otherwise the bot builds a self-hosted sub payload.

Then `panel_service.sync_inbounds()` caches inbounds so you can map plans to
specific inbound(s).

---

## 🗂 Migrations (Alembic)
```bash
alembic revision --autogenerate -m "change"   # after editing models
alembic upgrade head
alembic downgrade -1
```
`migrations/env.py` reads `DATABASE_URL` from `.env` and enables batch mode for
SQLite ALTERs automatically.

---

## 🔐 Security
- All secrets live in `.env` (git-ignored) — no hardcoding.
- Rate limiting + force-join + anti-fraud on free configs.
- Wallet changes always go through an auditable ledger.
See `docs/SECURITY.md` for the full checklist and hardening tips.

---

## 🧩 Extending
- **Full plan/panel/user admin CRUD**: implement the stubbed callbacks in
  `app/handlers/admin/admin_menu.py`.
- **Discount codes / reseller pricing**: tables exist (`discount_codes`,
  `user.price_multiplier`) — wire into `buy.py`.
- **Redis FSM + Celery**: swap `MemoryStorage` and APScheduler for horizontal scale.

Project tree and module map: `docs/ARCHITECTURE.md`.
