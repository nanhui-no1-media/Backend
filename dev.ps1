# dev.ps1 — One-click dev startup (PowerShell, Windows).
#
# Brings up the full stack: backend (Django runserver on :8000) + frontend
# (webpack-dev-server on :3000). Each server is launched in its OWN new
# PowerShell window so both run concurrently and you can watch both logs.
# We deliberately do NOT use Start-Job: jobs hide output and aren't friendly
# for a dev script. New windows survive this launcher exiting.
#
# Usage:  .\dev.ps1            (from anywhere)
#
# Flow:
#   1. git pull --ff-only  (warn + continue on divergence, never force-merge)
#   2. ensure .env exists  (copy from .env.example, never overwrite)
#   3. backend:  uv run python manage.py migrate  ->  runserver
#   4. frontend: npm install if node_modules missing -> npm run dev
# Each server ends up in its own window.

# Always operate from the script's own directory, regardless of CWD.
$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "WARNING: $msg" -ForegroundColor Yellow }

# ----------------------------------------------------------------------------
# 1. git pull --ff-only
# ----------------------------------------------------------------------------
Write-Step 'Pulling latest changes (git pull --ff-only)'
git pull --ff-only *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "git pull --ff-only failed (exit $LASTEXITCODE)."
    Write-Warn 'Local branch likely diverged from origin. NOT force-merging.'
    Write-Warn 'Resolve manually (rebase/merge), then re-run. Continuing with current tree...'
    # Intentionally do NOT abort: keep going to bring the stack up.
}

# ----------------------------------------------------------------------------
# 2. Ensure .env exists (never overwrite an existing one)
# ----------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath '.env')) {
    if (Test-Path -LiteralPath '.env.example') {
        Write-Step '.env missing — copying from .env.example'
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        Write-Host 'Created .env from .env.example. Edit it with your secrets.' -ForegroundColor Green
    } else {
        Write-Warn '.env AND .env.example are both missing. Backend config will be incomplete.'
    }
} else {
    Write-Host '.env already exists — leaving it untouched.' -ForegroundColor DarkGray
}

# ----------------------------------------------------------------------------
# 3. Backend — migrate, then runserver in a NEW window
# ----------------------------------------------------------------------------
Write-Step 'Running backend migrations (uv run python manage.py migrate)'
uv run python manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Warn "migrate exited with code $LASTEXITCODE. Starting runserver anyway..."
}

Write-Step 'Starting backend (Django runserver) in a new window'
# New window keeps running after this launcher exits; -NoExit keeps it open.
Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', `
    "Set-Location '$scriptRoot'; Write-Host 'BACKEND — Django runserver (:8000)' -ForegroundColor Cyan; uv run python manage.py runserver"

# ----------------------------------------------------------------------------
# 4. Frontend — npm install if needed, then npm run dev in a NEW window
# ----------------------------------------------------------------------------
Write-Step 'Starting frontend (frontend/) in a new window'
$feCmd = "Set-Location '$scriptRoot\frontend'; Write-Host 'FRONTEND — npm run dev (:3000)' -ForegroundColor Cyan; if (-not (Test-Path 'node_modules')) { Write-Host 'node_modules missing — running npm install'; npm install }; npm run dev"
Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $feCmd

Write-Step 'Dev stack launching'
Write-Host 'Backend  -> http://localhost:8000  (new window)' -ForegroundColor Green
Write-Host 'Frontend -> http://localhost:3000  (new window)' -ForegroundColor Green
Write-Host 'Close those windows to stop the servers.' -ForegroundColor DarkGray
