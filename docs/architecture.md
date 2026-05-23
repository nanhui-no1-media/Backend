# 架构概览

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.14 / Django 6.0 |
| 前端 | React 19 / TypeScript / Webpack 5 |
| 数据库 | SQLite（开发环境） |
| 包管理 | uv（后端）、npm（前端） |

## 整体架构

Django 单体应用，前端构建产物由 Django 直接服务：

```
用户请求 → Django (localhost:8000)
            ├── /admin/*     → Django Admin 后台
            ├── /auth/*      → JSON 认证接口
            ├── /static/*    → 静态文件（JS Bundle）
            └── /*           → SPA 入口（frontend/dist/index.html）
```

### 关键设计决策

- **非 API 架构**：前端由 Django 模板引擎直接服务，`{% csrf_token %}` 在 HTML 中注入 CSRF 令牌
- **CSRF 保护**：所有 POST 请求需携带 `X-CSRFToken` 请求头，前端从 `csrftoken` Cookie 中读取
- **Session 认证**：使用 Django 内置 `django.contrib.auth`，基于 Cookie 的 Session 机制
- **无公开注册**：用户由管理员在 Django Admin 后台手动创建
- **SPA 路由**：前端使用 React Router，Django 用 catch-all URL 将所有非后端路径导向 `index.html`

## 目录结构

```
Backend/
├── config/                # Django 项目配置
│   ├── settings.py        # 全局配置
│   ├── urls.py            # 根 URL 路由
│   └── wsgi.py
├── accounts/              # 用户认证应用
│   ├── views.py           # 视图函数
│   ├── forms.py           # Django 表单验证
│   ├── admin.py           # 管理后台扩展
│   ├── urls.py            # 认证路由
│   └── tests.py           # 单元测试
├── frontend/              # React 前端
│   ├── src/
│   │   ├── pages/         # 页面组件
│   │   ├── api/           # API 客户端
│   │   ├── components/    # 共享组件
│   │   └── App.tsx        # 路由配置
│   ├── public/            # HTML 模板
│   └── dist/              # 构建输出（gitignore）
├── static/                # 额外静态资源
└── docs/                  # 项目文档
```

## 认证流程

```
1. 访问任意页面 → Django 返回 index.html（含 {% csrf_token %}）
2. 前端读取 csrftoken Cookie → 设置请求头
3. POST /auth/login/ → Django 验证 → 创建 Session → 返回用户信息
4. 后续请求自动携带 sessionid Cookie → Django 识别用户身份
5. @login_required 保护需认证的接口 → 未登录返回 302 → 跳转 /login/
```
