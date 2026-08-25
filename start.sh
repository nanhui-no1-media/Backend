#!/usr/bin/env bash
# start.sh — 启动生产 WSGI（Gunicorn），并拉起同生命周期的更新守护进程。
#
# 设计：路径全部相对本脚本（仓库根），不硬编码 /srv/club。
#   - 由 systemd unit `club.service` 的 ExecStart 调用（Type=notify）；
#   - 也可手动 ./start.sh 前台跑（Ctrl-C 停），便于排障。
# 用 `exec` 让 gunicorn 顶替本 shell 成为 unit 主进程，sd_notify 才工作。
# 更新进程是 gunicorn 的兄弟（fork 后 exec）：停 club 时 systemd 清整个 cgroup，
# 不另写 club-updater.service。Apply 时对父进程 SIGHUP，避免 restart 把自己杀掉。
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

# 与 Gunicorn 同生共死。CLUB_SPAWN_UPDATER=0 可关（排障只起 web）。
if [ "${CLUB_SPAWN_UPDATER:-1}" != "0" ] && [ -x "$DIR/.venv/bin/python" ]; then
  export CLUB_UPDATER_SPAWNED=1
  "$DIR/.venv/bin/python" "$DIR/scripts/updater.py" &
fi

exec "$DIR/.venv/bin/gunicorn" \
  --workers "$GUNICORN_WORKERS" --threads "$GUNICORN_THREADS" \
  --bind "unix:$DIR/run/gunicorn.sock" \
  --access-logfile - --error-logfile - \
  config.wsgi:application
