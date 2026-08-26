# API 接口文档

本文档按当前仓库的实际代码整理，覆盖其主要公开接口。本文档不是“理论接口清单”，而是“现场运行中的接口地图”，更适合前端联调、后台使用和线上排障。

## 1. 接口约定

- 默认基础地址：`http://localhost:8000`（开发）
- 认证方式：基于 Django Session + Cookie，前端需随请求带上 CSRF
- 非 GET 请求通常需要 `X-CSRFToken`；前端可以从 cookie 中读取 `csrftoken`
- 这套项目以 API + SPA 模式开发，Django 侧大量使用 DRF `DefaultRouter`

### 1.1 通用返回状态

- `200 OK`：成功
- `201 Created`：创建成功
- `204 No Content`：删除/清空成功
- `400 Bad Request`：参数或状态错误
- `401 Unauthorized`：未登录或无权限
- `403 Forbidden`：登录但权限不够
- `404 Not Found`：资源不存在

### 1.2 重要说明

由于项目使用了嵌套路由，真实 URL 往往是“模块前缀 + router basename”，例如：

- `/news/news/`
- `/tasks/tasks/`
- `/tutorials/tutorials/`
- `/auth/identity-reviews/`

不要只看模块名单独理解 URL，实际访问时要带上最终路径。

## 2. 认证与账号相关接口

### 2.1 登录

```http
POST /auth/login/
```

请求体：

```json
{
  "username": "admin",
  "password": "your-password"
}
```

或者：

```json
{
  "email": "admin@example.com",
  "password": "your-password"
}
```

成功返回：

```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

常见错误：

- `400`：参数缺失、表单不合法
- `401`：用户名/密码错误

### 2.2 登出

```http
POST /auth/logout/
```

登录后调用，成功通常返回 `200`，并清理当前 Session。

### 2.3 当前用户信息

```http
GET /auth/me/
```

需要登录。返回当前登录用户基本信息及其能力/资料状态。

### 2.4 用户资料

```http
GET /auth/profile/
POST /auth/profile/update/
POST /auth/profile/change-password/
```

- `GET /auth/profile/`：读取当前用户资料
- `POST /auth/profile/update/`：更新头像、昵称、生日、性别、生涯简介等
- `POST /auth/profile/change-password/`：修改密码

头像上传通常使用 `multipart/form-data`，不要手动设置 `Content-Type`。

### 2.5 密码重置

```http
POST /auth/password-reset/
POST /auth/password-reset/confirm/
```

- `POST /auth/password-reset/`：请求重置链接
- `POST /auth/password-reset/confirm/`：确认新密码

开发环境下重置链接通常输出到控制台日志，便于本地测试。

### 2.6 验证与身份审核

```http
GET /auth/verification/
POST /auth/verification/email/bind/
POST /auth/verification/manual/submit/
GET /auth/identity-reviews/
```

这类接口用于：

- 查询当前账号验证状态
- 绑定邮箱验证
- 提交人工审核材料
- 管理员查看/处理身份审核记录

### 2.7 用户列表与用户资料概览

```http
GET /auth/users/
GET /auth/users/<id>/profile/
GET /auth/users/<id>/content/
```

用于：

- 获取用户列表
- 查看某个用户公开资料
- 查看该用户的内容贡献记录（依业务而定）

## 3. 新闻接口

```http
GET /news/news/
GET /news/news/<id>/
POST /news/news/
PUT /news/news/<id>/
PATCH /news/news/<id>/
DELETE /news/news/<id>/
```

适用于：

- 新闻列表
- 新闻详情
- 发布/编辑/删除新闻

## 4. 任务与标签接口

```http
GET /tasks/tasks/
GET /tasks/tasks/<id>/
POST /tasks/tasks/
PUT /tasks/tasks/<id>/
PATCH /tasks/tasks/<id>/
DELETE /tasks/tasks/<id>/

GET /tasks/tags/
GET /tasks/tags/<id>/
POST /tasks/tags/
PUT /tasks/tags/<id>/
PATCH /tasks/tags/<id>/
DELETE /tasks/tags/<id>/
```

这是任务系统的核心 API：

- 任务创建和状态流转
- 负责人/协作者分配
- 标签管理
- 任务筛选和详情

## 5. 活动接口

```http
GET /activities/activities/
GET /activities/activities/<id>/
```

目前项目中的活动模块较为成熟，涵盖：

- 众议（Deliberation）
- 征集（Collection）
- 展示（Exhibition）
- 活动状态与排期控制

对于活动详情页、投票或展示内容，通常由前端针对该 API 做业务聚合。

## 6. 提案与反馈接口

```http
GET /proposals/
GET /proposals/<id>/
POST /proposals/
```

从代码结构和语义来看，这部分主要面向：

- 反馈意见
- 匿名/署名提交
- 审核或处理记录

项目中有明确“匿名反馈”和“署名反馈”两种提交方式，匿名提交一般不记录提交者身份。

## 7. 教程接口

```http
GET /tutorials/tutorials/
GET /tutorials/tutorials/<id>/
POST /tutorials/tutorials/
PUT /tutorials/tutorials/<id>/
PATCH /tutorials/tutorials/<id>/
DELETE /tutorials/tutorials/<id>/
```

适用场景：

- 上传教程文档或视频
- 审核教程是否通过
- 统计浏览量/收藏等元数据

## 8. 消息、审核、关于、招聘等接口

这些模块大多按应用前缀直接挂路由：

```http
/messaging/
/reviews/
/about/
/recruitment/
/attachments/
/uploads/
/site-policy/
```

这部分接口一般用于：

- 站内消息
- 审核工作流
- 关于页编辑
- 招聘信息展示与审批
- 文件附件的上传/管理

## 9. 接口调试建议

### 9.1 调试时优先看以下内容

- `config/urls.py`
- 各应用下的 `urls.py`
- 相关 `views.py` / `ViewSet`
- `admin.py` 中的权限配置

### 9.2 典型请求示例

#### 登录

```bash
curl -c cookies.txt -X POST http://localhost:8000/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"your-password"}'
```

#### 获取当前用户

```bash
curl -b cookies.txt http://localhost:8000/auth/me/
```

#### 获取新闻列表

```bash
curl http://localhost:8000/news/news/
```

## 10. 推荐的协作原则

- 前后端联调时，先确认 URL path 是否正确，再看权限和 CSRF
- 任何改动接口，都要同步更新本文档和前端请求代码
- 对重要接口，建议保留最小示例响应，方便运营和维护人员快速排查

如果你后续要继续完善这份文档，下一步最值得补的是：

1. 各模块的真实请求体字段定义
2. 权限矩阵（谁能看/谁能改）
3. 关键接口的错误码和示例响应
4. 生产环境的常见问题排查清单
