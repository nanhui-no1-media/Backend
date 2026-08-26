# 社团管理系统 Backend

这是一个以 Django 为核心、React 前端为展示层的社团内部管理系统。当前代码结构已经覆盖了用户认证、任务管理、活动/众议/征集/展示、新闻发布、提案/反馈、教程、招聘、消息和站点策略等核心场景，适用于校内社团的日常运营和后台管理。

## 1. 当前项目状况

项目当前已经具备以下模块：

- 认证与账号：登录、注册、邮箱验证、人工审核、密码重置、用户资料、会话管理
- 内容管理：新闻、教程、关于页、站点政策
- 协作管理：任务、标签、消息、提案/反馈
- 活动管理：活动、众议、征集、展示、审核
- 招聘与审批：招聘信息、面试/审核流程
- 后台管理：Django Admin + 自定义视图 + 前端 SPA
- 运维能力：`deploy.sh` / `start.sh` 自动部署、systemd + Nginx + Gunicorn，适合内部低门槛生产环境

## 2. 技术栈

- 后端：Python 3.14 / Django 6.0
- 前端：React 19 / TypeScript / Webpack 5
- 数据库：SQLite（默认开发/生产都可用）
- 依赖管理：uv（Python） + npm（前端）
- 运行方式：Django 直接托管前端产物，Nginx + Gunicorn 作为生产网关

## 3. 快速开始

### 3.1 本地开发

```bash
# 安装 Python 依赖
uv sync

# 创建本地数据库
uv run python manage.py migrate

# 可选：创建超级管理员
uv run python manage.py createsuperuser

# 启动后端
uv run python manage.py runserver
```

前端开发：

```bash
cd frontend
npm install
npm run dev
```

默认前端开发地址通常为 `http://localhost:3000`，后端默认 `http://localhost:8000`。

### 3.2 生产构建

```bash
cd frontend
npm run build
```

构建产物写入 `frontend/dist/`，Django 会直接托管 SPA 页面与静态资源，无需额外部署独立前端服务。

## 4. 目录结构

```text
Backend/
├── accounts/             # 账号、验证、资料、权限相关
├── activities/           # 活动与活动类型（众议/征集/展示）
├── about/                # 关于页内容管理
├── attachments/          # 附件和上传处理
├── common/               # 公共组件、站点策略等
├── config/               # Django settings / urls / ASGI/WSGI
├── docs/                 # 项目文档
├── exam_board/           # 评审/考核相关功能
├── frontend/             # React 前端源代码与构建输出
├── messaging/            # 消息/通知
├── news/                 # 新闻模块
├── proposals/            # 反馈/意见/提案模块
├── recruitment/          # 招聘模块
├── reviews/              # 审核与审查逻辑
├── scripts/              # 运维脚本、更新脚本
├── static/               # 静态资源
├── tasks/                # 任务与标签模块
├── tutorials/            # 教程上传与审核模块
├── .env.example          # 环境变量模板
├── deploy.sh             # 生产部署脚本
├── start.sh              # 运行/重启脚本
├── manage.py             # Django 启动入口
├── pyproject.toml        # Python 项目配置
├── uv.lock               # uv 锁文件
└── README.md             # 项目入口文档
```

## 5. 文档导航

- API 接口文档：[`docs/api.md`](docs/api.md)
- 后台使用教程：[`docs/admin-guide.md`](docs/admin-guide.md)
- 运维与部署指南：[`docs/deployment.md`](docs/deployment.md)
- 架构概览：[`docs/architecture.md`](docs/architecture.md)
- ADR 设计记录：[`docs/adr/`](docs/adr/)

## 6. 主要入口和 URL

- 后台管理：`/admin/`
- 认证：`/auth/`
- 任务：`/tasks/`
- 新闻：`/news/`
- 活动：`/activities/`
- 提案/反馈：`/proposals/`
- 教程：`/tutorials/`
- 招聘：`/recruitment/`
- 附件上传：`/uploads/`
- 站点政策：`/site-policy/`

注意：本项目使用 Django + React 的单页架构，前端路由需要由 Django 回落到 `index.html`，非 API 路径都会进入 SPA 入口。

## 7. 常用命令

```bash
uv run python manage.py runserver        # 启动开发服务器
uv run python manage.py migrate          # 执行数据库迁移
uv run python manage.py makemigrations  # 生成迁移文件
uv run python manage.py test             # 运行测试
uv run python manage.py check            # 检查项目配置

cd frontend && npm run dev               # 启动前端开发服务器
cd frontend && npm run build             # 构建生产资源

sudo ./deploy.sh                         # 一键部署生产环境
./start.sh                              # 启动生产服务
```

## 8. 维护建议

- 生产环境请先复制 `.env.example` 为 `.env`，并按实际站点填充 SECRET_KEY、ALLOWED_HOSTS、邮箱参数等。
- 如果你需要给别人上手使用，优先为管理员配一份后台操作手册和一份运维手册，避免直接让运维/运营人员碰源码。
- 日常更新时优先走 `git pull` + `uv sync` + `npm run build` + `migrate` + `systemctl restart club` 这套流程。
- 代码需保持 DRF API 与前端能力一致，改动接口时同步更新文档和前端调用逻辑。

如果你是第一次接手这个项目，建议先读：

1. [docs/admin-guide.md](docs/admin-guide.md)
2. [docs/api.md](docs/api.md)
3. [docs/deployment.md](docs/deployment.md)
4. [docs/architecture.md](docs/architecture.md)
