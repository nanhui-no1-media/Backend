#!/usr/bin/env bash
# create-superuser.sh — 以 deploy 身份跑 manage.py createsuperuser（交互式填用户名/邮箱/密码）。
#
# 可 root 跑（自动切到 deploy），也可 deploy 直接跑。路径相对仓库根。
# 部署后用它建第一个超管，再去 /admin/ 把成员加入「社长」「信息组」组。
#
# 用法：  sudo ./create-superuser.sh                 # 交互式（按提示）
#         sudo ./create-superuser.sh --username admin --email a@b.c   # 只问密码
#         sudo DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_PASSWORD=... \
#              ./create-superuser.sh --noinput      # 全自动（CI / 脚本）
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_USER="${APP_USER:-deploy}"

# root → 切到 deploy 跑本脚本自身（exec 整脚本，无 sudo bash -lc 嵌套）
if [ "$(id -u)" = 0 ]; then
  echo "==> 以 root 启动，切换到 $APP_USER 身份执行"
  exec sudo -u "$APP_USER" bash "$0" "$@"
fi

# —— 以下以 deploy 身份 ——
cd "$DIR"
[ -f .env ] || cp .env.example .env
export HOME="$(getent passwd "$(id -un)" | cut -d: -f6)"   # 确定 uv 在 ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
set -a; . ./.env; set +a

echo "==> 创建超级管理员（按提示填用户名 / 邮箱 / 密码）："
exec uv run python manage.py createsuperuser "$@"
