# 运维与部署指南

本文档面向项目上线后的日常维护、升级、备份、排障和回滚。它不是源码说明书，而是“管理员使用时最需要的实战操作手册”。

## 1. 项目现状概述

当前项目采用的是：

- Django 6.0 后端
- React 19 前端
- SQLite 默认数据库
- Nginx + Gunicorn（ASGI / `UvicornWorker`）+ systemd 生产部署方式
- 一套 `scripts/install.sh` / `start.sh` 自动化脚本
- 消息推送：单进程 `InMemoryChannelLayer`（[ADR 0015](adr/0015-channels-without-redis.md)），**不**在 v1 引入 Redis

这套架构适合中小型社团内部站点、活动管理、内容发布、用户/审核场景。它的优点是：

- 部署相对简单
- 前后端统一托管
- 站点管理相对集中
- 不依赖复杂容器编排

## 2. 生产环境结构

生产环境通常是：

```text
浏览器
  ↓  HTTP/1.1，有证书后可 HTTP/2（HTTP/3 可选）
Nginx
  ├── /static/ → Django staticfiles
  ├── /media/ → 用户上传文件
  └── 其他（含 /ws/messaging/）
        ↓  一律 HTTP/1.1 + Upgrade（unix socket）
      Gunicorn UvicornWorker × 1 → Django ASGI
```

关键特征：

- Django 直接提供前端 `frontend/dist/` 产物
- `start.sh` 负责拉起 Gunicorn（**1 个** ASGI worker，`config.asgi:application`），并一起拉起更新守护进程
- WebSocket 走 `/ws/messaging/`，只推送私信 / 通知 / 当前评论区；挤号仍走 HTTP 中间件（[ADR 0015](adr/0015-channels-without-redis.md)）
- Nginx **对上游**须 HTTP/1.1 并转发 `Upgrade` / `Connection`；对外协议见下节
- `scripts/install.sh` 会处理依赖安装、（必要时）前端构建、SECRET_KEY / FRONTEND_URL / 超管、迁移、collectstatic、systemd 和 Nginx 配置
- **不要**在未引入 Redis 之前把 `--workers` 调到 >1：内存 channel layer 无法跨进程扇出，SQLite 也怕多写者
- **更新器不会改 Nginx**。已装过的机器要手改站点配置后 `nginx -t && systemctl reload nginx`

### Nginx 两段协议

两段连接协议可以不一样，**不要**按路径拆成「`/ws/` 走 1.1、别的走 HTTP/2」两套 `location`。一个 `location /` 反代到 unix socket 即可。

| 段 | 协议 |
|---|---|
| 浏览器 → nginx | HTTP/1.1；有 TLS 后开 HTTP/2；HTTP/3 可选 |
| nginx → Gunicorn | **一律 HTTP/1.1**（页面、API、WebSocket 的 `Upgrade` 都在这里） |

Uvicorn 在 unix socket 上只说 HTTP/1.1。`proxy_http_version` 管的是这一段；nginx 1.29.7 之前默认还是 HTTP/1.0，不写 `1.1` 则 WebSocket 握手失败。不要写 `proxy_http_version 2`。

安装脚本写入的站点文件（Debian：`/etc/nginx/sites-available/<服务名>`；阿里云/RHEL：`/etc/nginx/conf.d/<服务名>.conf`）已经是下面这份。已有 HTTPS 的 `server` **两边都要**带同一套反代头，不要只改 80。

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name club.example.com;
    client_max_body_size 20M;
    server_tokens off;

    location /static/ { alias /opt/club/staticfiles/; }
    location /media/   { alias /opt/club/media/; }

    location / {
        proxy_pass http://unix:/opt/club/run/gunicorn.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host       $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # 空闲 WebSocket 否则约 60s 被掐；前端会重连，但会抖
        proxy_read_timeout 7d;
        proxy_send_timeout 7d;
    }
}
```

有证书后对外开 HTTP/2：在 **443 的 `server`** 上开，反代段仍是上面的 1.1。nginx 1.25.1+ 可把 `http2` 从 `listen` 挪到指令 `http2 on;`。

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name club.example.com;
    ssl_certificate     /etc/letsencrypt/live/club.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/club.example.com/privkey.pem;
    client_max_body_size 20M;
    server_tokens off;
    add_header Strict-Transport-Security "max-age=31536000" always;
    # location /static/ /media/ 与 location / 与 80 相同
}
```

已上 HTTPS 的机器：更新器**不会**改 Nginx。在 443 的 `server` 里加上面两行（`server_tokens off` 与 HSTS），80 建议只 301 到 HTTPS，然后 `nginx -t && systemctl reload nginx`。Django 在 `DJANGO_DEBUG=0` 时也会对 HTTPS 响应发同一条 HSTS（`max-age=31536000`）；重复同值无害。不要开 `includeSubDomains` / `preload`，除非确认该域名下没有仍走 HTTP 的子域。

HTTP/3 同样只在 nginx 对外终结，对内仍 1.1。需模块支持，并放行 **UDP/443**：

```nginx
listen 443 quic reuseport;
listen 443 ssl;
http2 on;
http3 on;
add_header Alt-Svc 'h3=":443"; ma=86400' always;
```

发行版自带的 nginx（尤其阿里云）往往没有 HTTP/3 模块；没有就不要开，HTTP/2 已经够用。

## 3. 一次性部署

支持两条路：**已经 clone 了仓库**，或 **机器上还没有源码**（从 GitHub Release 拉包）。脚本自动识别 `apt` / `dnf` / `yum`，Nginx 同时写 Debian 的 `sites-available` 和 RHEL/阿里云 Linux 的 `conf.d/`。

### 3.1 独立安装（无需先 clone）

适合新机器、阿里云 Linux（非 Debian）等。Release 里已带 `frontend/dist`，不需要在服务器上装 Node。

```bash
# 公开仓库；管道必须带 -y（否则 read 会吞掉脚本自身）。私有仓库先 export GITHUB_TOKEN=...
curl -fsSL https://github.com/nanhui-no1-media/Backend/releases/latest/download/install.sh | sudo bash -s -- -y
```

或下载后再跑（便于看参数）：

```bash
curl -fsSL https://github.com/nanhui-no1-media/Backend/releases/latest/download/install.sh -o install.sh
sudo APP_DIR=/opt/club APP_USER=club SERVER_NAME=club.example.com \
    FRONTEND_URL=http://club.example.com SUPERUSER_PASSWORD='...' bash install.sh -y
```

指定历史版本：

```bash
sudo bash install.sh --from-release club-<sha>
```

默认安装到 `/opt/club`，服务用户 `club`。

### 3.2 仓库内就地部署

在 Ubuntu / Debian / 阿里云 Linux 上，于 clone 目录执行：

```bash
sudo ./scripts/install.sh
```

该脚本会：

- 按包管理器安装系统依赖（nginx、编译链、sqlite、curl…）
- 确认服务用户（仓库属主；独立安装则创建 `club`）
- 执行 `uv sync --frozen`（uv 会自行准备 Python 3.14）
- 仅当缺少 `frontend/dist` 时才 `npm ci && npm run build`
- 写入 `.env`：生成 `SECRET_KEY`、按域名/IP 填 `FRONTEND_URL` 与 `ALLOWED_HOSTS`、`DJANGO_DEBUG=0`
- 创建第一个超级用户（已有则跳过；密码可交互输入，非交互则随机并打印一次）
- 执行 `migrate` 和 `collectstatic`
- 写入 systemd 单元和 Nginx 配置（Debian 或 conf.d）
- 在 SELinux 开启时给 static/media/run 打标签，并尝试放行 firewalld 的 http
- 启动站点

跳过系统包：

```bash
sudo ./scripts/install.sh --skip-deps
```

### 3.3 手工启动

如果已经部署过，可以直接用：

```bash
./start.sh
```

它会：

- 导出 `.env`
- 创建 `run/` 目录
- 拉起更新守护进程
- `exec` 启动 Gunicorn（`-k uvicorn.workers.UvicornWorker --workers 1`，`config.asgi:application`）

## 4. 常用管理命令

```bash
sudo systemctl status club
sudo systemctl restart club
sudo systemctl stop club
sudo systemctl start club

sudo journalctl -u club -f
```

如果站点运行在 `nginx` 之后，也需要关注：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 5. 环境变量

所有敏感配置都通过 `.env` 管理，不建议直接修改 `config/settings.py`。

常见变量如下：

```bash
DJANGO_DEBUG=0
ALLOWED_HOSTS=example.com,127.0.0.1
FRONTEND_URL=http://example.com
SECRET_KEY=your-secret-key

EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password

TURNSTILE_SITE_KEY=...
TURNSTILE_SECRET_KEY=...

UPDATE_GITHUB_TOKEN=...
UPDATE_GITHUB_REPO=nanhui-no1-media/Backend
```

- `.env` 需要 `chmod 600`
- 不要将 `.env` 提交到 Git
- 服务启动前 `install.sh` 已写入 `SECRET_KEY`、`FRONTEND_URL`、`ALLOWED_HOSTS`；邮箱和 Turnstile 仍按需补。

## 6. 站点升级流程

生产环境请走 GitHub Release + 更新守护进程，不要在服务器上 `git pull` 再手工构建。

手动立刻升到最新 Release（忽略夜间窗口）：

```bash
cd /opt/club   # 或你的安装目录
set -a; . ./.env; set +a
.venv/bin/python scripts/updater.py --apply-now
```

回滚到任意一个以往的 Release（代码树；**不**还原 SQLite，以免丢上线后的数据）。SHA 可以是完整 hash、7 位以上前缀、或 `club-…` 标签；省略 SHA 则用本地最新的非当前包，否则用 GitHub 上当前版本的前一个 Release：

```bash
.venv/bin/python scripts/updater.py --rollback
.venv/bin/python scripts/updater.py --rollback abc1234
.venv/bin/python scripts/updater.py --rollback club-<fullsha>
```

自动更新失败时，守护进程仍会把**这一次** apply 前的文件 + 当时的 DB 快照拉回去（这和上面的主动 `--rollback` 不是同一条路径）。

`--apply-now` / `--rollback` 在终端里按 Ctrl+C 不会立刻杀掉半套树：当前步骤结束后会询问。尚未换文件则默认取消并撤下维护页；已经换文件则默认回滚（含这次 apply 前的 DB 快照）。也可以选择继续更新，或保持维护页（站点继续 503）再人工处理。无 TTY（守护进程）时走同一套默认，不提问。回滚进行中的 Ctrl+C 会被忽略，直到回滚结束。

建议发布后检查：

```bash
sudo systemctl status club
sudo journalctl -u club -n 50 --no-pager
```

## 7. 数据库与文件备份

### 7.1 SQLite 数据库

当前默认数据库是 SQLite，文件通常位于项目根目录或 Django 默认 DB 路径。运维时建议定期备份：

```bash
cp db.sqlite3 db.sqlite3.bak.$(date +%Y%m%d-%H%M%S)
```

### 7.2 媒体文件

用户上传的媒体一般保存在 `media/` 或由 `PRIVATE_MEDIA_ROOT` 指向的目录中。建议：

- 配置定期压缩归档
- 同步备份到对象存储或 NAS
- 保留最近 7～30 天的版本

### 7.3 代码回滚

优先用更新器钉到某个已发布的 runtime 包（见第 6 节 `--rollback`）。不要在生产树里 `git checkout`：独立安装的机器上往往没有 git 历史，Release 包也不含 `.git`。

若必须手工处理，确认 `backups/releases/club-<sha>.tar.gz` 还在，再执行 `--rollback <sha>`。Django 迁移不会自动反向；主动回滚只换代码与静态文件，数据库保持当前内容。

## 8. 日常排障

### 8.1 访问 502

常见原因：

- Gunicorn 未启动
- Nginx 配置错误
- `run/gunicorn.sock` 不存在

调试方式：

```bash
sudo systemctl status club
sudo journalctl -u club -n 100 --no-pager
ls -l /path/to/project/run/
```

### 8.2 登录失败 / 403

常见原因：

- CSRF 失效
- 域名未配置在 `ALLOWED_HOSTS`
- Session 未正确写入
- 账号未通过验证或权限不足

处理建议：

- 检查 `Cookie` 是否带 `csrftoken`、`sessionid`
- 检查浏览器网络是否跨域
- 检查 Django 日志和 browser console

### 8.3 资源加载失败

若静态文件或图片无法加载：

- 检查 `STATIC_ROOT` / `MEDIA_ROOT`
- 检查 Nginx 的 `location /static/` 和 `location /media/`
- 运行：

```bash
uv run python manage.py collectstatic --noinput
```

### 8.4 数据库锁住（database is locked）

这是 SQLite 在高并发写入时会出现的问题。处理方式：

- 降低并发 Worker 数
- 使用 WAL 模式
- 避免大量热点写操作同步发生
- 生产契约是 **`--workers 1`**（[ADR 0015](adr/0015-channels-without-redis.md)）；加 worker 须先上 Redis channel layer，另开 ADR

### 8.5 WebSocket 连不上 / 约一分钟断一次

页面还能用（评论、私信、通知走 HTTP），只是不实时推。

- 站点配置缺 `proxy_http_version 1.1` 或 `Upgrade` / `Connection`（更新器不会改 Nginx）
- 只改了 `listen 80` 的 `server`，HTTPS 的 443 块没有同一套反代头
- `start.sh` 仍是旧的 WSGI / 多 worker：须为 `UvicornWorker`、`--workers 1`、`config.asgi:application`
- 约 60 秒断一次：补 `proxy_read_timeout 7d;`（见第 2 节）

## 9. 监控和可观测性

建议至少留意下面几类日志：

```bash
sudo journalctl -u club -f
sudo tail -f /var/log/nginx/error.log
```

建议检查的关键指标：

- 站点启动状态
- 访问量/异常率
- 认证失败人数
- 媒体上传量
- 管理后台操作日志

## 10. 维护清单

每次发布前建议复核：

- `.env` 是否完整
- `ALLOWED_HOSTS` 是否包含真实域名
- `SECRET_KEY` 是否有效
- 迁移是否已执行
- 前端是否已构建
- Nginx + systemd 配置是否生效（上游 HTTP/1.1 + Upgrade；有 TLS 的 443 块同样要有）
- 关键页面是否能正常打开；登录后 `/ws/messaging/` 能握手

## 11. 结论

这套项目已经具备较完整的站点管理能力：从账号流程、任务协作、活动发布、教程审核到站点运营，都已经在代码层和脚本层形成了基本闭环。对运维和内容运营团队来说，最重要的工作不是“会改代码”，而是：

- 保证环境稳定
- 维护权限和账号
- 规范发布流程
- 及时备份和回滚
- 对关键页面和接口做定期检查

如果你要继续补充这个文档，下一步最有价值的扩展是：

1. 生产环境的“值班手册”
2. 账号/权限的操作说明
3. 发布流程 checklist
4. 线上异常处理的 SOP
