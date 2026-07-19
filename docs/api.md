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
{
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "permissions": {
      "can_manage_news": false,
      "can_manage_tasks": true,
      "can_assign_task": true,
      "can_manage_tags": true,
      "can_approve_proposals": true,
      "can_change_proposals": true,
      "can_view_feedback": true
    }
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

## 个人资料接口

### 获取个人资料

```
GET /auth/profile/
```

需登录，返回当前用户的完整资料。

成功响应 `200`：
```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "permissions": {
      "can_manage_news": false,
      "can_manage_tasks": true,
      "can_assign_task": true,
      "can_manage_tags": true,
      "can_approve_proposals": true,
      "can_change_proposals": true,
      "can_view_feedback": true
    }
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

### 更新个人资料

```
POST /auth/profile/update/
```

需登录，使用 `multipart/form-data`（支持头像上传）。

请求体（FormData）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `avatar` | 文件 | 否 | JPG/PNG/GIF/WebP，最大 2MB |
| `nickname` | 字符串 | 否 | 最长 50 字符 |
| `birthday` | 日期 | 否 | 格式 YYYY-MM-DD |
| `gender` | 字符串 | 否 | M=男, F=女, O=其他 |
| `bio` | 字符串 | 否 | 最长 500 字符 |

成功响应 `200`：同获取个人资料响应格式。

失败响应 `400`：
```json
{ "error": "头像文件不能超过 2MB" }
```

### 修改密码

```
POST /auth/profile/change-password/
```

需登录。

请求体：
```json
{ "old_password": "原密码", "new_password": "新密码" }
```

成功响应 `200`：
```json
{ "message": "密码修改成功" }
```

失败响应：
- `400` — 原密码不正确或新密码少于 8 个字符

## CSRF 要求

所有 POST 请求必须携带：
- 请求头 `X-CSRFToken`：从 Cookie `csrftoken` 中读取
- JSON 请求需设置 `Content-Type: application/json`
- FormData 请求（头像上传）**不要**手动设置 `Content-Type`，浏览器会自动处理

Django 模板中的 `{% csrf_token %}` 会在首次访问页面时设置 `csrftoken` Cookie。
