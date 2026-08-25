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

> 💡 **自动化**：仓库根两个脚本，路径全部相对仓库（在哪 clone 都行）——
> `sudo ./deploy.sh`（裸机一键：以仓库属主为服务用户、装依赖、**首次**在机上构建前端、写 `club.service` + nginx + sudoers、起服务）；
> `./start.sh`（拉起更新守护进程，再 `exec gunicorn`；被 unit 的 ExecStart 调，也可手动前台单跑）。
> 日常更新：`start.sh` 与 Gunicorn **同生共死**——`club` 在跑才预下载/夜间 apply，`systemctl stop club` 则停更新。紧急立即 apply 用 `uv run python scripts/updater.py --apply-now`。下面各节是脚本背后等价的手工步骤（便于理解 / 排障）。

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

**前提**：首次生产从 `git clone` 部署（`deploy.sh` 会在机上 `npm run build`，并把当前 `git HEAD` 写入 `run/applied-release`）。之后走 GitHub Release，**不再** `git pull` / 在机上 webpack。代码（含迁移）须已进 `main`，CI 才会打包。

### 1. 服务器准备（Ubuntu 24.04）

```bash
apt update && apt upgrade -y
apt install -y build-essential curl git nginx sqlite3 ca-certificates gnupg
# Ubuntu 仓库的 nodejs 与 npm 互斥（24.04 已知冲突）——Node.js 走 NodeSource 官方源（含 npm）
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
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
`SECRET_KEY` / `DJANGO_DEBUG` / `ALLOWED_HOSTS` / `FRONTEND_URL` / `EMAIL_*` / `TURNSTILE_*` / `UPDATE_GITHUB_*`；
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
# 自动更新（start.sh 与 Gunicorn 一同拉起；窗口/轮询在 /admin/「站点策略」）：
# UPDATE_GITHUB_TOKEN=...          # PAT，生产必填
# UPDATE_GITHUB_REPO=nanhui-no1-media/Backend   # 可选
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

`/etc/systemd/system/club.service`（`deploy.sh` 写入；`ExecStart` 指向 `start.sh`，由其拉起更新进程再 `exec gunicorn`）：

```ini
[Unit]
Description=Club Django (Gunicorn)
After=network.target

[Service]
Type=notify
User=deploy
Group=deploy
WorkingDirectory=/srv/club
ExecStart=/srv/club/start.sh
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

不另装 `club-updater.service`。`start.sh` 在 `exec gunicorn` 前后台启动 `scripts/updater.py`（环境变量 `CLUB_UPDATER_SPAWNED=1`）。二者同属 `club` 的 cgroup：`systemctl stop club` 会一起停掉。

```bash
sudo mkdir -p /srv/club/run && sudo chown deploy:deploy /srv/club/run
sudo systemctl daemon-reload
sudo systemctl enable --now club
sudo systemctl status club        # active (running)
```

已在跑、只想接上自动更新：把新 `start.sh` / `common/updater.py` 放到活树后 **`sudo systemctl restart club` 一次**即可（不必重跑 `deploy.sh`）。若曾装过 `club-updater.service`：`sudo systemctl disable --now club-updater`。

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

    # Gunicorn 重启空窗：Django 进程不在时，502 落到静态维护页（internal）
    error_page 502 /maintenance.html;
    location = /maintenance.html {
        alias /srv/club/static/maintenance.html;
        default_type text/html;
        charset utf-8;
        internal;
    }

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
5. `.env` 填好 `UPDATE_GITHUB_TOKEN` 后 `sudo systemctl restart club`。夜间窗口 / 轮询在 `/admin/`「站点策略」。

### 10. 后续更新（GitHub Release + 守护进程）

push 到 `main` 后，CI 并行跑后端测试与前端生产构建，二者都绿才打一份以 commit SHA 为 tag 的 GitHub Release。生产机上的更新进程由 **`start.sh` 随 `club` 拉起**：`club` 在跑则全天按站点策略轮询、把完整包预下载到 `backups/releases/`；**只在应用窗口内**抬维护、解包、切流量。`club` 停则更新停。更新路径**没有 git、没有 npm**。

首次部署仍是 `deploy.sh`（git clone 一次 + 机上 `npm run build`）；之后 `start.sh` 在这份已知可用的树上拉起 updater。日常更新**不需要 Node**。

#### CI：并行测试 / 构建 → SHA Release

工作流 [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)：

| Job | 何时 | 做什么 |
|-----|------|--------|
| `backend` | push / PR | `uv sync --frozen` → `uv run python manage.py test` |
| `frontend` | push / PR | Node 22：`npm ci && npm run build`，上传 `frontend/dist` 为 artifact |
| `release` | **仅** `main` 的 push，且 `needs: [backend, frontend]` | 把 dist 放回树内，`scripts/pack-release.sh` 打包，以 **commit SHA** 为 tag 建 Release |

附件（一份包，避免前后端各半错配）：

- `club-{sha}.tar.gz`：运行时树——Django 各 app（含 `apps.py` 的目录）、`config/`、`manage.py`、`pyproject.toml`、`uv.lock`、`scripts/`、`start.sh`、`frontend/dist/`
- `club-{sha}.tar.gz.sha256`：校验和不完整下载

打包**不包含**：`.git`、`.venv`、`node_modules`、`frontend/src`、`.env`、`db.sqlite3`、`media/`、`private_media/`、`run/`、`backups/`。

#### 守护进程（随 Gunicorn，不单独 systemd unit）

`start.sh` 在 `exec gunicorn` 前后台启动 `.venv/bin/python scripts/updater.py`（逻辑在 `common/updater.py`）。日志进同一个 `journalctl -u club`。`CLUB_SPAWN_UPDATER=0` 可只起 web。

每次 tick 先 `invalidate_policy_cache()` 再 `get_policy()`（进程内 locmem 不与 Gunicorn worker 共享；admin 保存不会自动打到 updater 进程）。循环：

1. `auto_update_enabled` 为关 → 跳过下载与应用。
2. 否则用 `UPDATE_GITHUB_TOKEN` 拉最新 Release。本地没有完整包（或校验失败）则下到 `backups/releases/club-{sha}.tar.gz.part`，sha256 对上后再改名。失败指数退避重试；`.part` 从不拿去 apply。若当前已应用 SHA 与最新不同、且那份包不在磁盘上，也会尽量预拉一份供回滚。
3. **下载不碰** `run/MAINTENANCE`。
4. 仅当磁盘上有比已应用更新的完整包、且当前落在窗口内、且未过截止时刻：对 `run/update.lock` 加锁后 apply。下载可与对外服务重叠；apply 不能与自己重叠。

成功 apply 后先撤维护页，再对 **Gunicorn 父进程 SIGHUP**（不 `systemctl restart club`，以免杀掉 updater），然后 `exec` 自身以加载新解包的脚本。手动 `--apply-now`（未由 start.sh 拉起）仍走 `systemctl restart club`。

#### 旋钮：admin「站点策略」vs `.env`

运营旋钮在 Django admin **站点策略** → fieldset「自动更新」，调用方只 `get_policy()`（[ADR-0010](adr/0010-runtime-site-policy.md)）。默认：

| 字段 | 默认 | 含义 |
|------|------|------|
| `auto_update_enabled` | True | 总开关；关则守护进程不下载、不应用 |
| `update_poll_interval_seconds` | 900 | 轮询间隔（秒） |
| `update_timezone` | `Asia/Shanghai` | 窗口时区；**不用** Django `TIME_ZONE` |
| `update_window_start_hour` / `update_window_end_hour` | 1 / 3 | 应用窗口 `[开始, 结束)` 整点小时 |
| `update_apply_cutoff_minutes_before_end` | 30 | 结束前 N 分钟起不再**开始** apply（默认即 02:30 后不新开） |
| `update_release_keep` | 3 | `backups/releases/` 保留完整包份数 |
| `update_db_backup_keep` | 5 | `backups/db-*.sqlite3` 保留份数 |

密钥 / 仓库名仍在 `.env`（改完须 `systemctl restart club`，updater 会随 start.sh 一起起来）：

- `UPDATE_GITHUB_TOKEN`：能读该仓库 Releases 的 PAT（生产必填；空则守护进程跳过下载）
- `UPDATE_GITHUB_REPO`：可选，缺省 `nanhui-no1-media/Backend`

#### 维护页

- 源是 **`run/MAINTENANCE` 文件**（JSON）。中间件只读这个文件、**不碰 DB**，所以 migrate 时也能出页面。
- **更新器**：apply 开始写入 `reason=update` 和当前步骤；维护页每 2 秒刷新，显示进度条与步骤文案。成功或健康回滚后撤旗标；若开始前运维已开，结束后会恢复运维拦截。
- **运维**：全站拦截（含 `/admin/`）。在服务器上：

```bash
uv run python manage.py maintenance on --message "磁盘扩容"
uv run python manage.py maintenance status
uv run python manage.py maintenance off
```

维护期间管理后台同样 503，所以结束运维只能走这条命令（或删掉 `run/MAINTENANCE`）。`off` 不会中止正在进行的更新，只会取消「更新结束后继续运维」。
- Gunicorn **reload（SIGHUP）** 那几秒 Django 不在：Nginx `error_page 502` 落到仓库内 `static/maintenance.html`（静态兜底，无实时进度）。**不要** `collectstatic --clear`。
- 回滚后仍不健康则**保持**维护旗标（步骤显示「正在回滚」）。

#### 应用与回滚

活树布局不变。解包**永不覆盖**：`.env`、`db.sqlite3`（及 journal/wal/shm）、`media/`、`private_media/`、`run/`、`backups/`、`.venv`、`.git`。

**Apply：**

1. 抬维护 + drain
2. SQLite `.backup` → `backups/db-{stamp}.sqlite3`（按 `update_db_backup_keep` 修剪；成功也不删这份快照）
3. 解包到 `backups/staging/`，再同步到活树
4. `uv sync --frozen`（读新的 `uv.lock`；**无 npm**）
5. `migrate` + `collectstatic --noinput`
6. 重载 web（spawned：SIGHUP 父进程 Gunicorn；手动 `--apply-now`：`systemctl restart club`）+ `is-active` 存活检查
7. 写 `run/applied-release` = SHA，保留该 tar 为 last-good，撤维护；守护进程再 `exec` 自身

**回滚**（任一步失败，或时钟已出窗口——窗口内 apply 会中途检查）：

1. 若文件已改且磁盘上有上一份 `backups/releases/club-{previous}.tar.gz`：同样解包同步（不访问 GitHub / git）
2. 若没有上一份包（例如守护进程驱动的第一次 apply）：文件保持当时状态，只尽量还原 DB 快照
3. 还原 apply 前的 DB 快照
4. `uv sync --frozen` + `collectstatic --noinput` + 重启
5. 把 `run/applied-release` 写回上一 SHA；仅当旧应用健康才撤维护

回滚用本地上一份完整包 + DB 快照，**不依赖** git / GitHub。

#### 手动立即更新

以部署用户跑（不要 sudo；`systemctl` 由 Python 走 sudoers 免密）：

```bash
cd <仓库目录>
uv run python scripts/updater.py --apply-now
```

必要时下载最新 Release，**忽略窗口**立即 apply（仍走同一把锁与回滚；不看 `auto_update_enabled`）。

日志：`sudo journalctl -u club -f`（Gunicorn 与更新进程同一 unit）。

### 11. 备份

SQLite 就是一个文件，定时冷备即可（用 `.backup` 避免拷到正在写的一半）：

```bash
sqlite3 /srv/club/db.sqlite3 ".backup '/backup/club-$(date +%F).sqlite3'"
```

`media/`（上传的图片/附件）单独打包：

```bash
tar czf /backup/media-$(date +%F).tar.gz -C /srv/club media
```

自动更新另在仓库内保留 `backups/releases/`（完整 tar，份数见 `update_release_keep`）和 `backups/db-*.sqlite3`（apply 前快照，份数见 `update_db_backup_keep`）。这是回滚用的本地包，不能代替机外冷备。

### 安全提醒

纯 HTTP 下，登录会话 cookie 明文传输（同网段可嗅探）。社团内网 / 低敏感场景一般可接受。
若以后要暴露到公网，请补 HTTPS：装 `certbot python3-certbot-nginx`，`sudo certbot --nginx -d club.example.com`，
并在 settings 里打开 `SECURE_SSL_REDIRECT` / `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE`（仅 HTTPS 下启用）。
