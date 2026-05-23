# 前端对接指南

本文档面向前端开发者，说明如何与 Django 后端对接。`frontend/` 目录下是测试用的 React 前端，正式前端可使用任意技术栈，只需遵循以下约定。

## 后端服务地址

开发环境：`http://localhost:8000`

如果前端使用独立 dev server（如 Vite、Webpack Dev Server），需要代理以下路径到后端：

| 路径 | 用途 |
|------|------|
| `/auth` | API 接口 |
| `/media` | 用户上传文件（头像等） |
| `/admin` | 管理后台（可选） |

也可以直接将前端构建产物交给 Django 服务，见下方「部署模式」。

## 认证机制

后端使用 **Session + CSRF**，不使用 JWT 或 Token。

### 1. CSRF 令牌

页面首次加载时，Django 通过 `csrftoken` Cookie 下发 CSRF 令牌。所有 POST/PUT/DELETE 请求必须携带：

```
X-CSRFToken: <csrftoken Cookie 的值>
```

获取方式（JavaScript）：

```javascript
function getCSRFToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}
```

### 2. Session Cookie

登录成功后 Django 设置 `sessionid` Cookie，浏览器自动携带。前端需确保请求配置：

```javascript
fetch(url, { credentials: "include" }); // 或 axios 的 withCredentials: true
```

### 3. 未登录处理

需要登录的接口，未登录时返回 HTTP `302` 重定向到 `/login/`。前端应检查响应状态码或先调用 `/auth/me/` 判断登录状态。

## API 约定

### 基础格式

- 所有 API 前缀：`/auth/`
- 请求体：JSON（除文件上传外）
- Content-Type：`application/json`
- 成功响应：HTTP 200 + JSON body
- 错误响应：HTTP 4xx + `{"error": "错误信息"}`

### 文件上传

使用 `multipart/form-data`，**不要** 手动设置 `Content-Type`（浏览器会自动添加 boundary）：

```javascript
const formData = new FormData();
formData.append("avatar", file);
formData.append("nickname", "昵称");

fetch("/auth/profile/update/", {
  method: "POST",
  headers: { "X-CSRFToken": getCSRFToken() },  // 不设 Content-Type
  body: formData,
  credentials: "include",
});
```

### 接口列表

完整接口文档见 [api.md](api.md)，核心接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/auth/login/` | POST | 登录（用户名或邮箱） |
| `/auth/logout/` | POST | 登出 |
| `/auth/me/` | GET | 获取当前用户信息 |
| `/auth/profile/` | GET | 获取个人资料 |
| `/auth/profile/update/` | POST | 更新资料（含头像上传） |
| `/auth/profile/change-password/` | POST | 修改密码 |
| `/auth/password-reset/` | POST | 请求密码重置邮件 |
| `/auth/password-reset/confirm/` | POST | 确认密码重置 |

### 响应格式

登录、获取用户信息、个人资料相关接口统一返回：

```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  },
  "profile": {
    "avatar": "/media/avatars/photo.jpg",
    "nickname": "管理员",
    "birthday": "2000-01-01",
    "gender": "M",
    "bio": "个人简介"
  }
}
```

其中 `avatar`、`birthday` 等可选字段未设置时为 `null`，`gender` 取值为 `"M"`（男）、`"F"`（女）、`"O"`（其他）或空字符串。

## 用户上传文件

头像等用户文件存储在 `/media/` 路径下，API 返回的是相对 URL（如 `/media/avatars/photo.jpg`）。

开发环境由 Django 直接服务，前端直接拼接为完整 URL 即可显示：

```html
<img src="/media/avatars/photo.jpg" />
```

如果前端使用独立 dev server，需代理 `/media` 到后端。

## URL 路由约定

Django 的路由规则：

| 路径 | 处理方 |
|------|--------|
| `/admin/*` | Django Admin |
| `/auth/*` | Django API |
| `/static/*` | 静态文件 |
| `/media/*` | 用户上传文件 |
| 其他所有路径 | 返回 `index.html`（SPA） |

前端路由不受限制，Django 会将所有非后端路径交给前端处理。路径选择只需避开 `/admin/`、`/auth/`、`/static/`、`/media/` 即可。

## 部署模式

前端有两种部署方式：

### 方式一：Django 服务（当前方式）

构建产物放入 Django 的静态文件目录，Django 统一服务前后端。

要求：
- `index.html` 放在 `frontend/dist/` 下，Django 作为模板渲染
- JS/CSS 等资源引用路径以 `/static/` 开头
- `index.html` 中需包含 `{% csrf_token %}`（Django 模板标签），用于初始化 CSRF Cookie

### 方式二：独立部署

前端独立部署（如 Nginx、CDN），通过反向代理将 API 请求转发到 Django。

要求：
- 配置反向代理将 `/auth/` 和 `/media/` 转发到 Django
- 跨域需配置 CORS（后端已配置 `django-cors-headers`，开发环境允许 `localhost:3000`）
- 生产环境需在 `config/settings.py` 的 `CORS_ALLOWED_ORIGINS` 中添加前端域名

## 测试前端参考

`frontend/` 目录下有一个 React 测试前端，可用于验证后端功能。技术栈：React 19 + TypeScript + Webpack 5。

运行方式：

```bash
cd frontend && npm install && npm run build
uv run python manage.py runserver    # 访问 localhost:8000
```

API 客户端参考实现见 `frontend/src/api/client.ts`。
