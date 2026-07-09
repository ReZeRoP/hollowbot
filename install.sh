#!/usr/bin/env bash
# ============================================================================
#  HollowBot — one-command installer
#
#  Usage (run on your server):
#     bash <(curl -fsSL https://raw.githubusercontent.com/ReZeRoP/hollowbot/main/install.sh)
#
#  What it does:
#   1) Checks for python3 + git
#   2) Clones (or updates) the repo into ./hollowbot
#   3) Creates an ISOLATED virtual environment (.venv) — never touches any
#      other Python packages on your system
#   4) Installs dependencies (SQLite-only by default, no compiler needed)
#   5) Creates .env from .env.example (first run only — never overwrites it)
#   6) Runs Alembic migrations to create the database schema
#
#  It will NOT start the bot for you — you must edit .env with your real
#  BOT_TOKEN / admin IDs / card info first. The script prints the exact next
#  steps at the end.
# ============================================================================
set -euo pipefail

REPO_URL="https://github.com/ReZeRoP/hollowbot.git"
INSTALL_DIR="${HOLLOWBOT_DIR:-hollowbot}"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
info() { printf "\033[36m==>\033[0m %s\n" "$1"; }
warn() { printf "\033[33m!!\033[0m %s\n" "$1"; }
die()  { printf "\033[31mERROR:\033[0m %s\n" "$1" >&2; exit 1; }

# --- 1) prerequisites ------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.11+ and re-run."
command -v git      >/dev/null 2>&1 || die "git not found. Install git and re-run."

PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
info "Using python3 $PY_VER"

# --- 2) clone or update -----------------------------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Existing installation found at ./$INSTALL_DIR — pulling latest changes..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  info "Cloning repository into ./$INSTALL_DIR ..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# --- 3) isolated virtual environment ---------------------------------------
if [ ! -d ".venv" ]; then
  info "Creating isolated virtual environment (.venv)..."
  python3 -m venv .venv
else
  info "Reusing existing .venv"
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- 4) dependencies ---------------------------------------------------------
info "Installing dependencies (SQLite-only, no compiler needed)..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# --- 5) .env ------------------------------------------------------------------
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn "Created .env from .env.example — YOU MUST EDIT IT before starting the bot."
else
  info ".env already exists — leaving it untouched."
fi
mkdir -p data backups

# --- 6) database schema -------------------------------------------------------
info "Setting up the database schema..."
if [ -z "$(ls -A migrations/versions 2>/dev/null | grep -v '.gitkeep' || true)" ]; then
  alembic revision --autogenerate -m "init" >/dev/null
fi
alembic upgrade head

echo ""
bold "✅ HollowBot installed at: $(pwd)"
echo ""
echo "Next steps:"
echo "  1) Edit the config:      nano .env"
echo "     (set BOT_TOKEN, SUPER_ADMIN_IDS, ADMIN_GROUP_ID, FORCE_JOIN_CHANNELS,"
echo "      CARD_NUMBER, CARD_HOLDER)"
echo "  2) Activate the venv:    source .venv/bin/activate"
echo "  3) (optional) Seed a demo panel + plans — edit PANEL_* in scripts_seed.py first:"
echo "                           python scripts_seed.py"
echo "  4) Start the bot:        python bot.py"
echo ""
echo "Prefer Docker instead? See README.md → 'Run with Docker'."
