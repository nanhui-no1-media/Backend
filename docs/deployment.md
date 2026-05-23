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

前端开发模式下，Webpack Dev Server 代理 `/auth` 和 `/admin` 到后端 `localhost:8000`。

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

Webpack 输出 `bundle.[hash].js` 到 `frontend/dist/`，`publicPath` 设为 `/static/`。

## 运行测试

```bash
uv run python manage.py test               # 运行所有测试
uv run python manage.py test accounts      # 运行 accounts 应用测试
```

## 部署清单

- [ ] 设置 `DEBUG = False`
- [ ] 更换 `SECRET_KEY` 为安全随机值
- [ ] 配置 `ALLOWED_HOSTS`
- [ ] 切换数据库（PostgreSQL 等）
- [ ] 配置生产邮件后端（替换 ConsoleEmailBackend）
- [ ] 运行 `npm run build` 构建前端
- [ ] 运行 `python manage.py collectstatic`
- [ ] 配置 WSGI 服务器（Gunicorn / uWSGI）
- [ ] 配置反向代理（Nginx）处理静态文件
