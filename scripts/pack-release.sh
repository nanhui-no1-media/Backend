#!/usr/bin/env bash
# pack-release.sh — pack the runtime tree into club-{sha}.tar.gz plus a
# sha256 sidecar for the GitHub Release (and later the updater daemon).
#
# Includes Django apps, config/, manage.py, pyproject.toml, uv.lock,
# scripts/, start.sh, .env.example, static/maintenance.html (nginx 502 page),
# and frontend/dist/. Excludes VCS, venv, secrets, local DB, media, and other
# runtime state.
#
# Usage: scripts/pack-release.sh [sha] [outdir]
#   sha     defaults to $GITHUB_SHA
#   outdir  defaults to the repository root
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SHA="${1:-${GITHUB_SHA:?pass commit SHA as arg 1 or set GITHUB_SHA}}"
OUT_DIR="${2:-$ROOT}"
mkdir -p "$OUT_DIR"
ARCHIVE="$OUT_DIR/club-${SHA}.tar.gz"

if [ ! -d frontend/dist ] || [ -z "$(ls -A frontend/dist 2>/dev/null)" ]; then
  echo "frontend/dist is missing or empty (download the frontend artifact first)" >&2
  exit 1
fi

INCLUDE=(
  config
  manage.py
  pyproject.toml
  uv.lock
  scripts
  start.sh
  .env.example
  frontend/dist
  static/maintenance.html
)

shopt -s nullglob
app_markers=(*/apps.py)
if [ ${#app_markers[@]} -eq 0 ]; then
  echo "no Django apps found (*/apps.py)" >&2
  exit 1
fi
for apps_py in "${app_markers[@]}"; do
  INCLUDE+=("${apps_py%/apps.py}")
done

for path in "${INCLUDE[@]}"; do
  if [ ! -e "$path" ]; then
    echo "missing required path: $path" >&2
    exit 1
  fi
done

echo "==> packing $(basename "$ARCHIVE")"
tar -czf "$ARCHIVE" \
  --exclude='__pycache__' \
  --exclude='*.py[cod]' \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='frontend/src' \
  --exclude='.env' \
  --exclude='db.sqlite3' \
  --exclude='db.sqlite3-journal' \
  --exclude='media' \
  --exclude='private_media' \
  --exclude='run' \
  --exclude='backups' \
  "${INCLUDE[@]}"

(
  cd "$OUT_DIR"
  sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256"
)

echo "==> wrote $ARCHIVE"
echo "==> wrote ${ARCHIVE}.sha256"
cat "${ARCHIVE}.sha256"
