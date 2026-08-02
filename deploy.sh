#!/usr/bin/env bash
# deploy.sh — 裸机一键部署（Ubuntu 24.04，Nginx + Gunicorn + SQLite + systemd）。
#
# 以 root 运行：装系统依赖、建 deploy 用户、把本仓库（=脚本所在目录）交给 deploy、
# uv sync、前端构建、写 .env、migrate + collectstatic、写 systemd unit（club.service）
# + nginx 站点 + sudoers（放行 deploy 免密 systemctl club）、enable 并启动。
#
# 路径全部相对本脚本（仓库根）派生，不硬编码 /srv/club —— 在哪 clone 就部署在哪。
# 幂等：可重复跑（用户/依赖已在则跳过）。
#
# 用法：  sudo ./deploy.sh                 # 裸机：装依赖+建用户+部署
#         sudo ./deploy.sh --skip-deps     # 跳过系统依赖与建用户（已自备 deps/deploy 用户时）
#         sudo ./deploy.sh -y              # 跳过确认
#         sudo SERVICE_NAME=club SERVER_NAME=club.example.com ./deploy.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_USER="${APP_USER:-deploy}"
SERVICE_NAME="${SERVICE_NAME:-club}"                 # ← 服务名固定 club
SERVER_NAME="${SERVER_NAME:-_}"                      # nginx server_name；_ = 任意（先用 IP 访问）
SYSTEMCTL="$(command -v systemctl || echo /usr/bin/systemctl)"

SKIP_DEPS=0
ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --skip-deps) SKIP_DEPS=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    *) echo "未知参数：$a（可用：--skip-deps / -y）" >&2; exit 2 ;;
  esac
done

# ---- 前置检查 ----
[ "$(id -u)" = 0 ] || { echo "deploy.sh 须以 root 运行：sudo ./deploy.sh" >&2; exit 1; }
[ -f "$DIR/manage.py" ] || { echo "未在仓库根找到 manage.py（$DIR）——请在 clone 的仓库里运行。" >&2; exit 1; }

echo "解析值："
echo "  仓库目录   DIR          = $DIR"
echo "  运行用户   APP_USER     = $APP_USER"
echo "  服务名     SERVICE_NAME = $SERVICE_NAME"
echo "  域名       SERVER_NAME  = $SERVER_NAME  （_ = 任意/IP）"
echo "  gunicorn socket        = $DIR/run/gunicorn.sock"
echo "  系统依赖               = $([ "$SKIP_DEPS" = 1 ] && echo '跳过（--skip-deps）' || echo '安装')"
echo
if [ "$ASSUME_YES" = 0 ]; then
  echo "将以 root 装系统依赖、建用户 $APP_USER、写 /etc/systemd/system/$SERVICE_NAME.service、"
  echo "/etc/nginx/sites-available/$SERVICE_NAME、/etc/sudoers.d/$SERVICE_NAME，并 enable+start。"
  read -rp "回车继续，Ctrl-C 中止。"
fi

# ---- 1. 系统依赖（幂等；--skip-deps 跳过）----
if [ "$SKIP_DEPS" = 1 ]; then
  echo "==> --skip-deps：跳过系统依赖安装与建用户（请确保 build-essential/nginx/sqlite3/node/npm 与 $APP_USER 已就绪）"
else
  # Ubuntu 仓库的 nodejs 与 npm 互斥（24.04 已知冲突，且 npm 缺一堆 node-* 依赖），
  # 故 Node.js 走 NodeSource 官方源（自带 npm、版本新），不装 Ubuntu 的 nodejs/npm。
  echo "==> 安装系统依赖：build-essential curl git nginx sqlite3 ca-certificates gnupg"
  apt-get update -y
  apt-get install -y build-essential curl git nginx sqlite3 ca-certificates gnupg

  if ! command -v node >/dev/null 2>&1; then
    echo "==> 安装 Node.js 22.x（NodeSource；自带 npm）"
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
  fi

  # ---- 2. deploy 用户（幂等）----
  if ! id -u "$APP_USER" >/dev/null 2>&1; then
    echo "==> 建用户 $APP_USER"
    adduser --disabled-password --gecos "" "$APP_USER"
  fi
fi

APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
[ -n "$APP_HOME" ] || { echo "用户 $APP_USER 不存在（--skip-deps 时需自备该用户）。" >&2; exit 1; }

# ---- 3. 仓库归属交给 deploy ----
echo "==> chown -R $APP_USER:$APP_USER $DIR"
chown -R "$APP_USER:$APP_USER" "$DIR"
install -d -o "$APP_USER" -g "$APP_USER" "$DIR/run" "$DIR/backups"

# 以 deploy 身份执行一段 bash（从 stdin 读 heredoc）。避免 sudo bash -lc 的嵌套转义地狱：
# heredoc 非引用定界 → $DIR/$APP_HOME 由外层展开烙进脚本；$HOME/$PATH 写成 \$ 形式留给 deploy 解析。
# 自动在脚本头加 set -euo pipefail，失败外溢（set -e）中止 deploy。
as_deploy_user() {
  local script; script="$(mktemp)"
  { echo 'set -euo pipefail'; cat; } > "$script"
  chown "$APP_USER:$APP_USER" "$script"
  sudo -u "$APP_USER" bash "$script"
  local rc=$?
  rm -f "$script"
  return $rc
}

# ---- 4. uv（deploy 用户）+ 装依赖 ----
echo "==> uv sync --frozen（以 $APP_USER 身份）"
as_deploy_user <<EOF
export HOME="$APP_HOME"
export PATH="\$HOME/.local/bin:\$PATH"
cd "$DIR"
if ! command -v uv >/dev/null 2>&1; then
  # 先下载到临时文件再执行，避免 curl 抖动时把错误页喂给 sh
  curl -fsSL https://astral.sh/uv/install.sh -o /tmp/uv-install.sh
  sh /tmp/uv-install.sh
  rm -f /tmp/uv-install.sh
fi
uv sync --frozen
EOF

# ---- 5. 前端构建（每次都 npm ci：按 lockfile 确定性安装，避免 node_modules 残缺/漏依赖）----
echo "==> 前端构建 → frontend/dist/"
as_deploy_user <<EOF
export HOME="$APP_HOME"
cd "$DIR/frontend"
npm ci
npm run build
EOF

# ---- 6. .env（缺则从模板复制；绝不覆盖既有，chmod 600）----
if [ ! -f "$DIR/.env" ]; then
  echo "==> 从 .env.example 复制 .env（请随后编辑填生产值）"
  sudo -u "$APP_USER" cp "$DIR/.env.example" "$DIR/.env"
fi
sudo -u "$APP_USER" chmod 600 "$DIR/.env"

# ---- 7. migrate + collectstatic（以 deploy，读 .env）----
echo "==> migrate + collectstatic"
as_deploy_user <<EOF
export HOME="$APP_HOME"
export PATH="\$HOME/.local/bin:\$PATH"
cd "$DIR"
set -a; . ./.env; set +a
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
EOF

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
visudo -c -f "/etc/sudoers.d/$SERVICE_NAME"

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
echo "   2) 建超管： sudo -u $APP_USER HOME=$APP_HOME bash -lc 'cd \"$DIR\" && set -a;. ./.env;set +a && uv run python manage.py createsuperuser'"
echo "   3) /admin/ 把成员加入「社长」「信息组」组（没组=没权限）。"
