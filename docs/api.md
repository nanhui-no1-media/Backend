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
- `429 Too Many Requests`：触发限流（注册 / 登录失败 / 匿名反馈等）

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
- `429`：登录失败次数过多（每 IP / 每用户名每小时上限见站点策略；只计失败）

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

## 6. 意见反馈接口

```http
GET /reviews/feedbacks/
GET /reviews/feedbacks/<id>/
POST /reviews/feedbacks/submit/
POST /reviews/feedbacks/<id>/close/
```

意见反馈是审核系统的一种案件（无对象投递箱），不是独立 app。匿名提交不记录提交者身份；署名提交可带附件。职员侧在 `/reviews` 队列处理。

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

## 7.1 考试看板（`/exam_board/` + `/ws/exam-board/`）

课表按 **考试 → 批次 → 科目场次** 嵌套（[ADR 0018](adr/0018-exam-board-batch-and-public-ws.md)）。读匿名开放；写需 `can_manage_exam`（`exam_board.add_exam`）。

```http
GET    /exam_board/exams/
GET    /exam_board/exams/latest/
GET    /exam_board/exams/<id>/
POST   /exam_board/exams/
PUT    /exam_board/exams/<id>/
DELETE /exam_board/exams/<id>/
GET    /exam_board/exams/clock/
GET    /exam_board/errata/current/
POST   /exam_board/errata/
POST   /exam_board/errata/dismiss/
GET    /ws/exam-board/
```

写入考试时 `batches[].subjects[]` 带 `name` / `exam_date` / `start_time` / `end_time`。授时返回 Asia/Shanghai。误刊 `multipart`：`text` 与可选 `image`；同一时刻至多一条未撤回。WebSocket 匿名可连，下行 `{ "event": "exam"|"errata"|"errata_cleared", "payload": {} }`，HTTP 仍是事实源。

## 8. 消息模块契约（`/messaging/` + `/ws/messaging/`）

本节是消息重置后的 HTTP / WebSocket 契约（[ADR 0015](adr/0015-channels-without-redis.md)、[ADR 0016](adr/0016-comment-thread-vs-dm.md)）。实现按此对齐；**不要**另起 `/messages/` 等前缀。会话子资源沿用现网路径；评论区 / 通知 / 禁言 / 横幅按下列资源名落地。

公开 `GET /site-policy/` 已返回站点策略快照；`comment_max_depth` 与 Turnstile（`turnstile_enabled` / `turnstile_site_key`）随快照出现，不另开接口。secret 不下发；两项密钥都空则关闭。

### 8.1 评论区

按宿主取恰好一条；可改状态（`open` 开放 / `muted` 评论区禁言 / `closed` 彻底关闭）。

```http
GET    /messaging/threads/?news=<id>
GET    /messaging/threads/?activity=<id>
GET    /messaging/threads/?task=<id>
PATCH  /messaging/threads/<id>/
```

`PATCH` 体为 `{ "status": "open" | "muted" | "closed" }`。彻底关闭后普通读者看不到该区；协管仍可 GET。

### 8.2 评论

根评论分页（页大小 20），子评论嵌在同一 payload（社团体量，不另开子列表）。

```http
GET    /messaging/comments/?thread=<id>
POST   /messaging/comments/
POST   /messaging/comments/<id>/retract/
POST   /messaging/comments/<id>/delete/
```

- 发表：已验证、未被全站禁言、能看见宿主、评论区为开放
- 撤回：作者、限时、且无子评论
- 删除：协管墓碑（「该评论已删除」），子树保留

### 8.3 私信（会话）

只保留 1:1 私信。列表不返回任务/申报会话。

```http
GET    /messaging/conversations/
GET    /messaging/conversations/<id>/
GET    /messaging/conversations/messages/?conversation_id=<id>
GET    /messaging/conversations/unread_count/
POST   /messaging/conversations/start_private/
POST   /messaging/conversations/<id>/send_message/
POST   /messaging/conversations/<id>/mark_read/
```

**删除（不再提供）：**

```http
POST   /messaging/conversations/get_task_conversation/
POST   /messaging/conversations/get_proposal_conversation/
```

任务讨论改走该任务的评论区；申报事件改走通知。

### 8.4 通知

```http
GET    /messaging/notifications/
GET    /messaging/notifications/unread_count/
POST   /messaging/notifications/<id>/mark_read/
POST   /messaging/notifications/mark_read/
```

最后一条为全部已读。通知不是私信副本；待办收件箱不再含会话项。

### 8.5 全站禁言

```http
POST   /messaging/mutes/
POST   /messaging/mutes/lift/
GET    /messaging/mutes/me/
```

禁言 / 解除需 `can_mute_user`。`GET …/me/` 给当前用户自己的状态，供 SPA 禁用评论与私信输入框。被禁言者仍可登录、阅读、接收私信与通知。

### 8.6 横幅公告

```http
GET    /messaging/banners/current/
```

`AllowAny`，无需 session。全站同一时刻至多一条。写入只走 Django admin，无产品侧写接口。

### 8.7 WebSocket（只推送）

```http
GET    /ws/messaging/
```

已登录（session cookie）；进组 `user_{id}`。客户端可发 `{ "action": "subscribe_thread"|"unsubscribe_thread", "thread_id": <id> }` 订当前评论区。下行 `{ "event": "dm"|"notification"|"comment", "payload": { ids } }`（`message_id` / `comment_id` / `notification_id` / `thread_id` / `conversation_id`）。无输入状态、已读回执、在线、历史回放。挤号不走此连接。访客无 socket，横幅靠 8.6 轮询。

## 9. 审核、关于、招聘等接口

这些模块大多按应用前缀直接挂路由：

```http
/reviews/
/about/
/recruitment/
/attachments/
/uploads/
/site-policy/
```

这部分接口一般用于：

- 审核工作流
- 关于页编辑
- 招聘信息展示与审批（含招生公告）
- 文件附件的上传/管理
- 公开站点策略快照

## 10. 接口调试建议

### 10.1 调试时优先看以下内容

- `config/urls.py`
- 各应用下的 `urls.py`
- 相关 `views.py` / `ViewSet`
- `admin.py` 中的权限配置

### 10.2 典型请求示例

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

## 11. 推荐的协作原则

- 前后端联调时，先确认 URL path 是否正确，再看权限和 CSRF
- 任何改动接口，都要同步更新本文档和前端请求代码
- 对重要接口，建议保留最小示例响应，方便运营和维护人员快速排查

如果你后续要继续完善这份文档，下一步最值得补的是：

1. 各模块的真实请求体字段定义
2. 权限矩阵（谁能看/谁能改）
3. 关键接口的错误码和示例响应
4. 生产环境的常见问题排查清单
