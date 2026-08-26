# 运维与部署指南

本文档面向项目上线后的日常维护、升级、备份、排障和回滚。它不是源码说明书，而是“管理员使用时最需要的实战操作手册”。

## 1. 项目现状概述

当前项目采用的是：

- Django 6.0 后端
- React 19 前端
- SQLite 默认数据库
- Nginx + Gunicorn + systemd 生产部署方式
- 一套 `scripts/install.sh` / `start.sh` 自动化脚本

这套架构适合中小型社团内部站点、活动管理、内容发布、用户/审核场景。它的优点是：

- 部署相对简单
- 前后端统一托管
- 站点管理相对集中
- 不依赖复杂容器编排

## 2. 生产环境结构

生产环境通常是：

```text
浏览器
  ↓
Nginx
  ├── /static/ → Django staticfiles
  ├── /media/ → 用户上传文件
  └── 其他请求 → Gunicorn → Django
```

关键特征：

- Django 直接提供前端 `frontend/dist/` 产物
- `start.sh` 负责拉起 Gunicorn，并一起拉起更新守护进程
- `scripts/install.sh` 会处理依赖安装、（必要时）前端构建、SECRET_KEY / FRONTEND_URL / 超管、迁移、collectstatic、systemd 和 Nginx 配置

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
- `exec` 启动 Gunicorn

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
- 对低流量站点，通常 `--workers 2` 已足够

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
- Nginx + systemd 配置是否生效
- 关键页面是否能正常打开

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
