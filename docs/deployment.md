# 运维与部署指南

本文档面向项目上线后的日常维护、升级、备份、排障和回滚。它不是源码说明书，而是“管理员使用时最需要的实战操作手册”。

## 1. 项目现状概述

当前项目采用的是：

- Django 6.0 后端
- React 19 前端
- SQLite 默认数据库
- Nginx + Gunicorn + systemd 生产部署方式
- 一套 `deploy.sh` / `start.sh` 自动化脚本

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
- `deploy.sh` 会处理依赖安装、前端构建、迁移、collectstatic、systemd 和 Nginx 配置

## 3. 一次性部署

### 3.1 先准备环境

建议在 Ubuntu 24.04 之类的 Linux 服务器上执行：

```bash
sudo ./deploy.sh
```

该脚本会：

- 安装系统依赖
- 创建/确认服务用户
- 执行 `uv sync --frozen`
- 执行前端 `npm ci && npm run build`
- 生成 `.env`（如果不存在）
- 执行 `migrate` 和 `collectstatic`
- 写入 systemd 单元和 Nginx 配置
- 启动站点

### 3.2 手工启动

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
- 服务启动前务必确认 `ALLOWED_HOSTS`、`FRONTEND_URL` 和站点域名一致

## 6. 站点升级流程

建议遵循下面流程：

```bash
cd /path/to/project
git pull
uv sync --frozen
cd frontend && npm ci && npm run build && cd ..
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
sudo systemctl restart club
```

如果你使用的是自动更新脚本，更新时也可以让 `start.sh`/updater 自行处理，但仍建议在发布前做一次手动检查：

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

如果上线后出现问题，可使用：

```bash
git log --oneline -n 20
```

再切回稳定版本：

```bash
git checkout <commit-or-tag>
uv sync --frozen
cd frontend && npm ci && npm run build && cd ..
uv run python manage.py migrate
sudo systemctl restart club
```

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
