# API 接口文档

所有认证接口前缀为 `/auth/`，需携带 CSRF 令牌。

## 认证接口

### 登录

```
POST /auth/login/
```

请求体：
```json
{ "username": "用户名", "password": "密码" }
```
或
```json
{ "email": "邮箱", "password": "密码" }
```

成功响应 `200`：
```json
{ "user": { "id": 1, "username": "admin", "email": "admin@example.com" } }
```

失败响应：
- `400` — 参数缺失或无效
- `401` — 凭据错误

### 登出

```
POST /auth/logout/
```

需登录（`@login_required`），未登录返回 `302` 跳转到 `/login/`。

成功响应 `200`：
```json
{ "message": "Logged out" }
```

### 获取当前用户

```
GET /auth/me/
```

需登录（`@login_required`），未登录返回 `302`。

成功响应 `200`：
```json
{ "user": { "id": 1, "username": "admin", "email": "admin@example.com" } }
```

## 密码重置

### 请求重置链接

```
POST /auth/password-reset/
```

请求体：
```json
{ "email": "user@example.com" }
```

成功响应 `200`：
```json
{ "message": "If an account with that email exists, a reset link has been sent." }
```

开发环境下重置链接输出到 Django 控制台。

### 确认重置

```
POST /auth/password-reset/confirm/
```

请求体：
```json
{ "uid": "MQ", "token": "abc123...", "new_password": "新密码" }
```

成功响应 `200`：
```json
{ "message": "Password has been reset successfully." }
```

失败响应 `400` — 链接无效、令牌过期或参数缺失。

## CSRF 要求

所有 POST 请求必须携带：
- 请求头 `X-CSRFToken`：从 Cookie `csrftoken` 中读取
- 请求头 `Content-Type: application/json`

Django 模板中的 `{% csrf_token %}` 会在首次访问页面时设置 `csrftoken` Cookie。
