#!/usr/bin/env bash
# deploy.sh — 裸机一键部署（Ubuntu 24.04，Nginx + Gunicorn + SQLite + systemd）。
#
# 以 root 运行：装系统依赖、建 deploy 用户、把本仓库（=脚本所在目录）交给 deploy、
# uv sync、前端构建、写 .env、migrate + collectstatic、写 systemd unit（club.service）
# + nginx 站点 + sudoers（放行 deploy 免密 systemctl club）、enable 并启动。
#
# 路径全部相对本脚本（仓库根）派生，不硬编码 /srv/club —— 在哪 clone 就部署在哪。
# 幂等：可重复跑（用户/依赖已在则跳过）。开始前会打印解析值并要求确认。
#
# 用法：  sudo ./deploy.sh                  # 交互确认
#         sudo SERVICE_NAME=club SERVER_NAME=club.example.com ./deploy.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_USER="${APP_USER:-deploy}"
SERVICE_NAME="${SERVICE_NAME:-club}"                 # ← 服务名固定 club
SERVER_NAME="${SERVER_NAME:-_}"                      # nginx server_name；_ = 任意（先用 IP 访问）
SYSTEMCTL="$(command -v systemctl || echo /usr/bin/systemctl)"

# ---- 前置检查 ----
[ "$(id -u)" = 0 ] || { echo "deploy.sh 须以 root 运行：sudo ./deploy.sh" >&2; exit 1; }
[ -f "$DIR/manage.py" ] || { echo "未在仓库根找到 manage.py（$DIR）——请在 clone 的仓库里运行。" >&2; exit 1; }
command -v nginx >/dev/null 2>&1 || NEED_APT=1 || true
command -v git    >/dev/null 2>&1 || NEED_APT=1 || true

echo "解析值："
echo "  仓库目录   DIR          = $DIR"
echo "  运行用户   APP_USER     = $APP_USER"
echo "  服务名     SERVICE_NAME = $SERVICE_NAME"
echo "  域名       SERVER_NAME  = $SERVER_NAME  （_ = 任意/IP）"
echo "  gunicorn socket        = $DIR/run/gunicorn.sock"
echo
echo "将以 root 装系统依赖、建用户 $APP_USER、写 /etc/systemd/system/$SERVICE_NAME.service、"
echo "/etc/nginx/sites-available/$SERVICE_NAME、/etc/sudoers.d/$SERVICE_NAME，并 enable+start。"
read -rp "回车继续，Ctrl-C 中止。"

# ---- 1. 系统依赖（幂等）----
echo "==> 安装系统依赖：nginx nodejs npm git curl build-essential sqlite3"
apt-get update -y
apt-get install -y build-essential curl git nginx nodejs npm sqlite3

# ---- 2. deploy 用户（幂等）----
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  echo "==> 建用户 $APP_USER"
  adduser --disabled-password --gecos "" "$APP_USER"
fi

# ---- 3. 仓库归属交给 deploy ----
echo "==> chown -R $APP_USER:$APP_USER $DIR"
chown -R "$APP_USER:$APP_USER" "$DIR"
install -d -o "$APP_USER" -g "$APP_USER" "$DIR/run" "$DIR/backups"

# ---- 4. uv（deploy 用户）+ 装依赖 ----
echo "==> uv sync --frozen（以 $APP_USER 身份）"
sudo -iu "$APP_USER" bash -lc "
  cd '$DIR'
  command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH=\"\$HOME/.local/bin:\$PATH\"
  uv sync --frozen
"

# ---- 5. 前端构建（每次都 npm ci：按 lockfile 确定性安装，避免 node_modules 残缺/漏依赖）----
echo "==> 前端构建 → frontend/dist/"
sudo -iu "$APP_USER" bash -lc "cd '$DIR/frontend' && npm ci && npm run build"

# ---- 6. .env（缺则从模板复制；绝不覆盖既有，chmod 600）----
if [ ! -f "$DIR/.env" ]; then
  echo "==> 从 .env.example 复制 .env（请随后编辑填生产值）"
  sudo -u "$APP_USER" cp "$DIR/.env.example" "$DIR/.env"
fi
sudo -u "$APP_USER" chmod 600 "$DIR/.env"

# ---- 7. migrate + collectstatic（以 deploy，读 .env）----
echo "==> migrate + collectstatic"
sudo -iu "$APP_USER" bash -lc "
  cd '$DIR'
  export PATH=\"\$HOME/.local/bin:\$PATH\"
  set -a; . ./.env; set +a
  uv run python manage.py migrate
  uv run python manage.py collectstatic --noinput
"

# ---- 8. systemd unit（路径派生；ExecStart 调 start.sh）----
echo "==> 写 /etc/systemd/system/$SERVICE_NAME.service"
cat > "/etc/systemd/system/$SERVICE_NAME.service" <<UNIT
[Unit]
Description=Club Django (Gunicorn)
After=network.target

[Service]
Type=notify
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$DIR
ExecStart=$DIR/start.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

# ---- 9. nginx 站点（路径派生；\$host 等 nginx 变量用反斜杠护住）----
echo "==> 写 /etc/nginx/sites-available/$SERVICE_NAME"
cat > "/etc/nginx/sites-available/$SERVICE_NAME" <<NGINX
server {
    listen 80;
    server_name $SERVER_NAME;
    client_max_body_size 20M;

    location /static/ { alias $DIR/staticfiles/; }
    location /media/   { alias $DIR/media/; }

    location / {
        proxy_pass http://unix:$DIR/run/gunicorn.sock;
        proxy_set_header Host              \$host;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/$SERVICE_NAME"
nginx -t
systemctl reload nginx

# ---- 10. sudoers：放行 deploy 免密管理本服务（update.sh 用）----
echo "==> 写 /etc/sudoers.d/$SERVICE_NAME（$APP_USER 免密 systemctl $SERVICE_NAME）"
cat > "/etc/sudoers.d/$SERVICE_NAME" <<SUDOERS
$APP_USER ALL=(ALL) NOPASSWD: $SYSTEMCTL start $SERVICE_NAME, $SYSTEMCTL stop $SERVICE_NAME, $SYSTEMCTL restart $SERVICE_NAME, $SYSTEMCTL is-active $SERVICE_NAME
SUDOERS
chmod 440 "/etc/sudoers.d/$SERVICE_NAME"
visudo -cf

# ---- 11. enable + start ----
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo
echo "✅ 部署完成。"
echo "   访问： http://${SERVER_NAME/#_/localhost}   （SERVER_NAME=_ 时用服务器 IP）"
echo "   日志： sudo journalctl -u $SERVICE_NAME -f"
echo
echo "⚠️  收尾（必做）："
echo "   1) 编辑 $DIR/.env 填生产值（DJANGO_DEBUG=0 / ALLOWED_HOSTS=你的域名,IP / SECRET_KEY / EMAIL_* / TURNSTILE_*），"
echo "      再：sudo systemctl restart $SERVICE_NAME"
echo "   2) 建超管： sudo -iu $APP_USER bash -lc 'cd \"$DIR\" && set -a;. ./.env;set +a && uv run python manage.py createsuperuser'"
echo "   3) /admin/ 把成员加入「社长」「信息组」组（没组=没权限）。"
