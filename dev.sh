#!/usr/bin/env bash
# dev.sh — One-click dev startup (Bash / Git Bash / WSL / Linux / macOS).
#
# Brings up the full stack: backend (Django runserver on :8000) + frontend
# (webpack-dev-server on :3000). Both are long-running servers. We start each
# in the BACKGROUND with logs tee'd to files, then `wait` so this script stays
# alive as long as either server runs. Ctrl-C here kills both.
#
# Why not tmux/new-terminals? To stay dependency-free and portable across
# Git Bash (Windows), WSL, and bare Linux/macOS. Logs are tailed live AND
# appended to dev-backend.log / dev-frontend.log in the repo root.
#
# Usage:  ./dev.sh            (from anywhere)
#
# Flow:
#   1. git pull --ff-only  (warn + continue on divergence, never force-merge)
#   2. ensure .env exists  (copy from .env.example, never overwrite)
#   3. backend:  uv run python manage.py migrate  ->  runserver
#   4. frontend: npm install if node_modules missing -> npm run dev

set -u

# Always operate from the script's own directory, regardless of CWD.
cd "$(dirname "$0")" || { echo "FATAL: cannot cd to script dir" >&2; exit 1; }

step()  { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
warn()  { printf '\033[33mWARNING: %s\033[0m\n' "$1"; }

BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
    echo
    echo "==> Stopping dev servers..."
    [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

# ----------------------------------------------------------------------------
# 1. git pull --ff-only
# ----------------------------------------------------------------------------
step 'Pulling latest changes (git pull --ff-only)'
if ! git pull --ff-only >/dev/null 2>&1; then
    warn 'git pull --ff-only failed.'
    warn 'Local branch likely diverged from origin. NOT force-merging.'
    warn 'Resolve manually (rebase/merge), then re-run. Continuing with current tree...'
    # Intentionally do NOT abort: keep going to bring the stack up.
fi

# ----------------------------------------------------------------------------
# 2. Ensure .env exists (never overwrite an existing one)
# ----------------------------------------------------------------------------
if [ ! -f '.env' ]; then
    if [ -f '.env.example' ]; then
        step '.env missing — copying from .env.example'
        cp -- '.env.example' '.env'
        printf '\033[32mCreated .env from .env.example. Edit it with your secrets.\033[0m\n'
    else
        warn '.env AND .env.example are both missing. Backend config will be incomplete.'
    fi
else
    printf '\033[90m.env already exists — leaving it untouched.\033[0m\n'
fi

# ----------------------------------------------------------------------------
# 3. Backend — migrate, then runserver in the background
# ----------------------------------------------------------------------------
step 'Running backend migrations (uv run python manage.py migrate)'
if ! uv run python manage.py migrate; then
    warn 'migrate failed. Starting runserver anyway...'
fi

step 'Starting backend (Django runserver :8000) in background'
# `tee` mirrors output to the terminal and to the log file at the same time.
uv run python manage.py runserver 2>&1 | tee dev-backend.log &
BACKEND_PID=$!

# ----------------------------------------------------------------------------
# 4. Frontend — npm install if needed, then npm run dev in the background
# ----------------------------------------------------------------------------
step 'Starting frontend (frontend/) in background'
(
    cd frontend || { warn 'frontend/ dir missing — skipping frontend'; exit 1; }
    if [ ! -d 'node_modules' ]; then
        echo 'node_modules missing — running npm install'
        npm install || { warn 'npm install failed'; exit 1; }
    fi
    npm run dev
) 2>&1 | tee dev-frontend.log &
FRONTEND_PID=$!

step 'Dev stack launching'
printf '\033[32mBackend  -> http://localhost:8000  (logs: dev-backend.log)\033[0m\n'
printf '\033[32mFrontend -> http://localhost:3000  (logs: dev-frontend.log)\033[0m\n'
printf '\033[90mCtrl-C here to stop both servers.\033[0m\n'

# Stay alive while either server runs. EXIT/INT/TERM trap cleans them up.
wait
