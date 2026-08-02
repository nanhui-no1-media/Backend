#!/usr/bin/env bash
# update.sh — 生产更新：备份 → 停服 → 拉取 → 装依赖 → 前端构建 → migrate →
# collectstatic → 启动 → 存活检查。任一步失败 → 自动回滚到更新前版本并重启旧版。
#
# 以 deploy 用户跑。systemctl 那几步走 sudo（由 deploy.sh 写入的 /etc/sudoers.d/club
# 放行 `systemctl start/stop/restart/is-active club`，免密）。
# 路径全部相对本脚本（仓库根）。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

SERVICE="${SERVICE:-club}"
BACKUPS="$DIR/backups"
DB="$DIR/db.sqlite3"
KEEP="${BACKUP_KEEP:-5}"
mkdir -p "$BACKUPS"

# uv 装在 deploy 的 ~/.local/bin；登录脚本通常已带，兜底一下。
export PATH="$HOME/.local/bin:$PATH"
# .env（migrate / collectstatic 需要 Django settings）
[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a

OLD_HEAD="$(git rev-parse HEAD)"
STAMP="$(date +%Y%m%d-%H%M%S)"
DB_BAK="$BACKUPS/db-$STAMP.sqlite3"

# ---- 回滚：恢复 DB 快照 + 回旧 commit + 重建旧产物 + 启动旧版 ----
rollback() {
  trap - ERR          # 防递归
  set +e              # 回滚内部步骤失败不中断，尽量恢复
  echo
  echo "❌ 更新失败，自动回滚到 $OLD_HEAD …" >&2
  git reset --hard "$OLD_HEAD"
  uv sync --frozen
  ( cd frontend && npm ci && npm run build ) || echo "⚠️  旧版前端重建失败，请人工排查" >&2
  if [ -f "$DB_BAK" ]; then
    cp -f "$DB_BAK" "$DB"
    echo "已还原 DB 快照 $DB_BAK" >&2
  fi
  uv run python manage.py collectstatic --noinput || echo "⚠️  collectstatic 失败" >&2
  sudo systemctl start "$SERVICE" || echo "⚠️  旧版重启失败，服务未起来——请人工介入" >&2
  echo "⚠️  已回滚到 $OLD_HEAD 并尝试启动旧版。请排查失败原因后重试。" >&2
}

# ---- 前置：工作树须干净（否则回滚的 git reset 会丢未提交改动）----
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "工作树有未提交改动，拒绝更新（请先 commit / stash）。" >&2
  exit 1
fi
if ! git fetch --quiet; then
  echo "git fetch 失败（网络？），未做任何改动。" >&2
  exit 1
fi

echo "==> 停止服务 $SERVICE"
sudo systemctl stop "$SERVICE" || true

echo "==> 备份数据库 → $DB_BAK"
if command -v sqlite3 >/dev/null 2>&1 && [ -f "$DB" ]; then
  sqlite3 "$DB" ".backup '$DB_BAK'"     # 一致性备份，避免拷到写一半的页
elif [ -f "$DB" ]; then
  cp "$DB" "$DB_BAK"                     # 已停服，cp 也安全
fi
# 清理旧备份，保留最近 KEEP 份
ls -1t "$BACKUPS"/db-*.sqlite3 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

# ---- 关键步骤：任一失败触发 rollback ----
trap rollback ERR

echo "==> git pull --ff-only"
git pull --ff-only

echo "==> uv sync --frozen"
uv sync --frozen

echo "==> 前端构建（npm ci 按 lockfile 确定性安装）"
( cd frontend && npm ci && npm run build )

echo "==> migrate"
uv run python manage.py migrate

echo "==> collectstatic"
uv run python manage.py collectstatic --noinput

echo "==> 启动服务并存活检查"
sudo systemctl start "$SERVICE"
sleep 3
if ! sudo systemctl is-active --quiet "$SERVICE"; then
  echo "❌ 服务启动后非 active" >&2
  false   # 触发 ERR → rollback
fi

trap - ERR
echo
echo "✅ 更新完成：$OLD_HEAD → $(git rev-parse HEAD)"
echo "日志：journalctl -u $SERVICE -f"
