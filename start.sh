#!/usr/bin/env bash
# start.sh — 启动生产 WSGI（Gunicorn）。
#
# 设计：路径全部相对本脚本（仓库根），不硬编码 /srv/club。
#   - 由 systemd unit `club.service` 的 ExecStart 调用（Type=notify）；
#   - 也可手动 ./start.sh 前台跑（Ctrl-C 停），便于排障。
# 用 `exec` 让 gunicorn 顶替本 shell 成为 unit 主进程，sd_notify 才工作。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# .env 缺则从模板兜底复制（生产应由 deploy.sh 就位）；不覆盖既有。
[ -f .env ] || cp .env.example .env
# 导出 .env 供 gunicorn/Django 读（手动单跑时需要；systemd 调用时也幂等）。
set -a; . ./.env; set +a

# socket 目录（相对仓库根）；systemd unit 与 nginx 都指向这里。
mkdir -p "$DIR/run"

GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_THREADS="${GUNICORN_THREADS:-4}"

exec "$DIR/.venv/bin/gunicorn" \
  --workers "$GUNICORN_WORKERS" --threads "$GUNICORN_THREADS" \
  --bind "unix:$DIR/run/gunicorn.sock" \
  --access-logfile - --error-logfile - \
  config.wsgi:application
