#!/usr/bin/env bash
# reset.sh — 清除 deploy.sh 生成的部署产物，便于反复调试 / 干净重新部署。
#
# root 运行。删：
#   系统：/etc/systemd/system/club.service、/etc/nginx/sites-{available,enabled}/club、
#         /etc/sudoers.d/club；并 systemctl stop/disable club、daemon-reload、nginx reload。
#   app ：.venv、frontend/node_modules、frontend/dist、staticfiles、run、backups、
#         db.sqlite3、.env。
# 不删（deploy.sh 幂等会复用）：deploy 用户、apt 装的系统包；以及运行期上传目录
#   media/、private_media/（用户数据，非部署产物）。
#
# 路径全部相对本脚本（仓库根）。
# 用法：  sudo ./reset.sh                # 全清（含 .env 与 DB）
#         sudo ./reset.sh --keep-data    # 保留 .env 与 db.sqlite3，只重置部署管线
#         sudo ./reset.sh -y             # 跳过确认
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="${SERVICE_NAME:-club}"
KEEP_DATA=0
ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --keep-data) KEEP_DATA=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    *) echo "未知参数：$a（可用：--keep-data / -y）" >&2; exit 2 ;;
  esac
done

[ "$(id -u)" = 0 ] || { echo "reset.sh 须以 root 运行：sudo ./reset.sh [--keep-data] [-y]" >&2; exit 1; }

echo "将清除以下 deploy 产物（仓库目录 $DIR）："
echo "  系统：/etc/systemd/system/$SERVICE_NAME.service"
echo "        /etc/nginx/sites-available/$SERVICE_NAME（含 sites-enabled 软链）"
echo "        /etc/sudoers.d/$SERVICE_NAME"
echo "        → systemctl stop/disable $SERVICE_NAME、daemon-reload、nginx reload"
echo "  app ：.venv  frontend/node_modules  frontend/dist  staticfiles  run  backups"
if [ "$KEEP_DATA" = 1 ]; then
  echo "        .env、db.sqlite3  【保留】（--keep-data）"
else
  echo "        .env  db.sqlite3"
fi
echo "【不删】deploy 用户、apt 系统包、media/、private_media/（运行期上传，非部署产物）"
echo
if [ "$ASSUME_YES" = 0 ]; then
  read -rp "确认清除？输入 yes 继续： " ans
  [ "$ans" = "yes" ] || { echo "已取消。"; exit 0; }
fi

# ---- 1. 停服 + 禁用（服务不存在则忽略）----
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

# ---- 2. 删系统文件 ----
rm -f "/etc/systemd/system/$SERVICE_NAME.service"
rm -f "/etc/nginx/sites-enabled/$SERVICE_NAME"
rm -f "/etc/nginx/sites-available/$SERVICE_NAME"
rm -f "/etc/sudoers.d/$SERVICE_NAME"
systemctl daemon-reload
if nginx -t 2>/dev/null; then systemctl reload nginx || true; fi

# ---- 3. 删 app 层产物（归属 deploy，root 可删）----
cd "$DIR"
rm -rf .venv frontend/node_modules frontend/dist staticfiles run backups
rm -f db.sqlite3 db.sqlite3-journal
if [ "$KEEP_DATA" = 1 ]; then
  echo "保留 .env 与 db.sqlite3（--keep-data）"
else
  rm -f .env
fi

echo "✅ 已清除。重新干净部署：sudo ./deploy.sh"
