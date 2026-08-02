# 开发与部署指南

## 开发环境

### 启动后端

```bash
uv sync                                    # 安装依赖
uv run python manage.py migrate            # 数据库迁移
uv run python manage.py createsuperuser    # 创建管理员
uv run python manage.py runserver          # 启动服务器 (localhost:8000)
```

### 前端开发模式

```bash
cd frontend
npm install
npm run dev                                # 开发服务器 (localhost:3000, HMR)
```

前端开发模式下，Webpack Dev Server 代理 `/auth`、`/admin` 和 `/media` 到后端 `localhost:8000`。

### 生产构建

```bash
cd frontend
npm run build                              # 输出到 frontend/dist/
```

构建后 Django 直接服务前端，无需单独部署前端服务。

## 用户管理

系统不提供公开注册，用户由管理员在后台创建：

1. 访问 `/admin/`
2. 在「用户」模块中点击「添加用户」
3. 填写用户名和密码，保存

管理后台已汉化，提供增强的列表筛选和搜索功能。

## 静态文件

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `STATIC_URL` | `/static/` | 静态文件 URL 前缀 |
| `STATIC_ROOT` | `staticfiles/` | collectstatic 输出目录 |
| `STATICFILES_DIRS` | `frontend/dist/`, `static/` | 静态文件搜索目录 |
| `MEDIA_URL` | `/media/` | 用户上传文件 URL 前缀 |
| `MEDIA_ROOT` | `media/` | 用户上传文件存储目录 |

Webpack 输出 `bundle.[hash].js` 到 `frontend/dist/`，`publicPath` 设为 `/static/`。

## 运行测试

```bash
uv run python manage.py test               # 运行所有测试
uv run python manage.py test accounts      # 运行 accounts 应用测试
```

## 生产部署（Linux · HTTP + SQLite）

> 栈：**Nginx + Gunicorn(WSGI) + SQLite + systemd**；uv 管理（自带托管 CPython 3.14）。
> 不含 HTTPS、不含 PostgreSQL——社团内部 / 低敏感场景的极简部署。

> 💡 **自动化**：仓库根有四个脚本，路径全部相对仓库（在哪 clone 都行）——
> `sudo ./deploy.sh`（裸机一键：建 deploy 用户、装依赖、构建、写 `club.service`+nginx+sudoers、起服务）；
> `./start.sh`（`exec gunicorn`，被 unit 的 ExecStart 调，也可手动前台单跑）；
> `./update.sh`（备份 DB → 停服 → `git pull --ff-only` → uv sync → 前端 build → migrate → collectstatic → 启动 + 存活检查；**任一步失败自动回滚**到旧版）；
> `sudo ./reset.sh`（清除 deploy 生成的全部产物——systemd/nginx/sudoers 配置 + `.venv`/`node_modules`/`dist`/`staticfiles`/`run`/`backups`/`.env`/`db.sqlite3`，便于反复调试干净重部署；`--keep-data` 保留 `.env` 与 DB）。
> 下面各节是脚本背后等价的手工步骤（便于理解 / 排障）。

### 架构（单源 SPA）

React 构建到 `frontend/dist/`，由 Django 经 `TEMPLATES` + `STATICFILES_DIRS` + catch-all `re_path` 直接伺服。线上是**一个域名**：

```
浏览器 ──HTTP──▶ Nginx ──┬─ /static/ /media/  → 直读磁盘（前端打包资源、上传文件）
                         └─ 其余（含 SPA 路由 + /auth /news /tasks … API）
                             → Gunicorn(WSGI) → Django → SQLite 文件
```

- `WSGI_APPLICATION='config.wsgi.application'` → 用 **Gunicorn**（不需要 asgi/uvicorn）。
- 会话 cookie 认证（`SessionAuthentication` + `CsrfViewMiddleware`）。
- `DATABASES` = SQLite（dev/prod 同样）。
- Python 3.14 由 **uv 托管的 CPython** 提供，**不需要系统装 3.14**。
- 默认组（社长 / 信息组）由数据迁移 `news/0002_create_info_group`、`accounts/0002_seed_default_groups` 自动种入。

**前提**：生产从 `git clone` 部署，确保最新代码（含迁移）已提交推送到 `main`。

### 1. 服务器准备（Ubuntu 24.04）

```bash
apt update && apt upgrade -y
apt install -y build-essential curl git nginx nodejs npm
adduser --disabled-password --gecos "" deploy
mkdir -p /srv/club && chown deploy:deploy /srv/club
```

### 2. uv + 拉代码 + 装依赖

```bash
sudo -iu deploy
cd /srv/club
git clone https://github.com/nanhui-no1-media/Backend.git .
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv sync --frozen          # 读 uv.lock；uv 自动拉托管版 CPython 3.14，建好 .venv（含 gunicorn）
```

### 3. 构建前端

```bash
cd /srv/club/frontend
npm ci && npm run build   # 产出 frontend/dist/，Django 直接伺服
cd /srv/club
```

### 4. 配置 / 密钥（已 env 化，**勿手改 settings.py**）

`config/settings.py` 在 #27 已改为环境变量驱动（`python-dotenv` 顶部 `load_dotenv()`，读
`SECRET_KEY` / `DJANGO_DEBUG` / `ALLOWED_HOSTS` / `FRONTEND_URL` / `EMAIL_*` / `TURNSTILE_*`；
邮件后端按 `EMAIL_HOST_USER` 自动选 163 SMTP 或 console；`PRIVATE_MEDIA_ROOT` 私有存储）。
模板见入库的 `.env.example`——**复制成 `.env` 填值即可，不要再去改 settings.py**。

> - **不要**加 `SESSION_COOKIE_SECURE` / `SECURE_SSL_REDIRECT` 之类——HTTP 下会把会话 cookie 直接弄失效。
> - 同源 SPA 的 CSRF 一般同源就过。真遇到 403，再加 `CSRF_TRUSTED_ORIGINS`（在 settings 里解析一个 env）。
> - 邮件：配了 `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` 即走 163 SMTP 发验证/重置邮件；留空则 console（打到 journalctl）。

### 5. 环境变量（`.env`，`chmod 600`，**不进 git**）

照 `.env.example` 填：

```bash
DJANGO_DEBUG=0
ALLOWED_HOSTS=club.example.com,1.2.3.4
FRONTEND_URL=http://club.example.com
SECRET_KEY=...                 # 强随机；内部工具可省略（回退 dev 占位）
# 发邮件才填（163 授权码，非登录密码）：
# EMAIL_HOST_USER=...
# EMAIL_HOST_PASSWORD=...
# TURNSTILE_SITE_KEY=...  TURNSTILE_SECRET_KEY=...
```

### 6. migrate + 静态 + 超级用户

```bash
cd /srv/club
set -a; source .env; set +a
uv run python manage.py migrate            # 数据迁移自动种入「社长」「信息组」组
uv run python manage.py collectstatic --noinput
uv run python manage.py createsuperuser
```

### 7. Gunicorn + systemd

`/etc/systemd/system/club.service`：

```ini
[Unit]
Description=Club Django (Gunicorn)
After=network.target

[Service]
Type=notify
User=deploy
Group=deploy
WorkingDirectory=/srv/club
EnvironmentFile=/srv/club/.env
ExecStart=/srv/club/.venv/bin/gunicorn \
          --workers 2 --threads 4 \
          --bind unix:/srv/club/run/gunicorn.sock \
          --access-logfile - --error-logfile - \
          config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /srv/club/run && sudo chown deploy:deploy /srv/club/run
sudo systemctl daemon-reload
sudo systemctl enable --now club
sudo systemctl status club        # active (running)
```

<details>
<summary>遇到 <code>database is locked</code>（可选加固）</summary>

SQLite 写并发有锁，`--workers 2` 对低流量站一般够。真频繁报错，在 `config/settings.py` 末尾加这段（WAL + 忙等待，显著缓解写竞争）：

```python
from django.db.backends.signals import connection_created

def _sqlite_pragma(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        with connection.cursor() as c:
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA busy_timeout=5000;")

connection_created.connect(_sqlite_pragma)
```
</details>

### 8. Nginx（HTTP）

`/etc/nginx/sites-available/club`：

```nginx
server {
    listen 80;
    server_name club.example.com;
    client_max_body_size 20M;          # 头像 / 任务附件上传上限

    location /static/ { alias /srv/club/staticfiles/; }
    location /media/   { alias /srv/club/media/; }

    location / {
        proxy_pass http://unix:/srv/club/run/gunicorn.sock;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/club /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

访问 `http://club.example.com` 应能打开。

### 9. 上线后清单

1. `/admin/` 用超级用户登录 → 把成员加入「社长」「信息组」组。**没组就没权限**，整套权限系统靠它。
2. 发一条已发布新闻 → 首页「社团动态」出头条。
3. 建一条已通过活动申报 → feed 出活动卡。
4. 匿名看首页：能看到新闻 + 活动，**看不到任务卡**（任务仅登录成员可见，feed 服务端强制）。

### 10. 后续更新流程

一键（推荐，自带备份 + 失败自动回滚，以 `deploy` 用户跑）：

```bash
cd <仓库目录>
./update.sh
```

等价的手工步骤：

```bash
cd <仓库目录>
git pull && uv sync --frozen
( cd frontend && npm ci && npm run build )
set -a; source .env; set +a
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
sudo systemctl restart club
```

日志：`sudo journalctl -u club -f`。

### 11. 备份

SQLite 就是一个文件，定时冷备即可（用 `.backup` 避免拷到正在写的一半）：

```bash
sqlite3 /srv/club/db.sqlite3 ".backup '/backup/club-$(date +%F).sqlite3'"
```

`media/`（上传的图片/附件）单独打包：

```bash
tar czf /backup/media-$(date +%F).tar.gz -C /srv/club media
```

### 安全提醒

纯 HTTP 下，登录会话 cookie 明文传输（同网段可嗅探）。社团内网 / 低敏感场景一般可接受。
若以后要暴露到公网，请补 HTTPS：装 `certbot python3-certbot-nginx`，`sudo certbot --nginx -d club.example.com`，
并在 settings 里打开 `SECURE_SSL_REDIRECT` / `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE`（仅 HTTPS 下启用）。
