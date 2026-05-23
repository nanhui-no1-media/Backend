# Backend

Django + React 全栈项目。

## 技术栈

- **后端**: Python 3.14 / Django 6.0 / SQLite
- **前端**: React 19 / TypeScript / Webpack 5
- **包管理**: uv（后端）、npm（前端）

## 快速开始

### 环境准备

```bash
# 安装后端依赖
uv sync

# 数据库迁移
uv run python manage.py migrate

# 创建管理员账号
uv run python manage.py createsuperuser

# 启动开发服务器
uv run python manage.py runserver
```

### 前端开发

```bash
cd frontend
npm install
npm run dev          # 开发服务器 (localhost:3000)
```

### 生产构建

```bash
cd frontend
npm run build        # 构建到 frontend/dist/
```

构建后由 Django 直接服务前端页面，无需单独部署前端。

## 项目结构

```
Backend/
├── config/           # Django 项目配置
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/         # 用户认证应用
│   ├── views.py      # 登录、登出、密码重置
│   ├── forms.py      # Django 表单验证
│   ├── admin.py      # 管理后台配置
│   └── urls.py
├── frontend/         # React 前端
│   ├── src/
│   │   ├── pages/    # 页面组件
│   │   ├── api/      # API 客户端
│   │   └── App.tsx   # 路由配置
│   ├── public/       # HTML 模板
│   └── dist/         # 构建输出
├── static/           # 静态资源
└── docs/             # 项目文档
```

## 文档

详见 [docs/](docs/) 目录。

## 常用命令

| 命令 | 说明 |
|------|------|
| `uv run python manage.py runserver` | 启动开发服务器 |
| `uv run python manage.py migrate` | 执行数据库迁移 |
| `uv run python manage.py makemigrations` | 生成迁移文件 |
| `uv run python manage.py test` | 运行测试 |
| `cd frontend && npm run dev` | 启动前端开发服务器 |
| `cd frontend && npm run build` | 前端生产构建 |
