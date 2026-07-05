# 前端对接指南

本文档面向前端开发者，说明如何与 Django 后端对接。`frontend/` 目录下是测试用的 React 前端，正式前端可使用任意技术栈，只需遵循以下约定。

## 后端服务地址

开发环境：`http://localhost:8000`

如果前端使用独立 dev server（如 Vite、Webpack Dev Server），需要代理以下路径到后端：

| 路径 | 用途 |
|------|------|
| `/auth` | 账号、个人资料、用户列表等接口 |
| `/tasks` | 任务、标签、附件接口 |
| `/messaging` | 站内消息、任务讨论接口 |
| `/media` | 用户上传文件（头像、附件等） |
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
| `/auth/users/` | GET | 用户列表（任务表单选人用；返回 `{results:[{id,username,nickname,avatar}]}`，**无 `email`**） |

> 任务、标签、附件、站内消息与任务讨论的接口见下方「任务系统」「站内消息与任务讨论」两节。

### 响应格式

登录、获取用户信息、个人资料相关接口统一返回：

```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "is_president": true
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

其中 `avatar`、`birthday` 等可选字段未设置时为 `null`，`gender` 取值为 `"M"`（男）、`"F"`（女）、`"O"`（其他）或空字符串。`user.is_president` 为布尔值，表示当前用户是否属于「社长」组（见「任务系统 · 权限模型」）。

### 列表查询（分页 / 过滤 / 搜索 / 排序）

任务、会话等列表接口遵循 Django REST Framework 约定：

- **分页**：返回 `{count, next, previous, results}`，数据在 `results` 数组中；少数接口（如 `/auth/users/`）不分页，直接返回 `{results: [...]}`。建议前端统一处理：响应体有 `results` 字段就取 `results`，否则取整体。
- **过滤**：按字段精确匹配，如 `GET /tasks/tasks/?status=pending&priority=high`。
- **搜索**：`?search=关键词`（任务匹配标题/描述，标签匹配名称）。
- **排序**：`?ordering=-created_at`（负号表示倒序）。任务可排序字段：`created_at`、`completed_at`、`priority`、`status`。

## 用户上传文件

头像等用户文件存储在 `/media/` 路径下，API 返回的是相对 URL（如 `/media/avatars/photo.jpg`）。

开发环境由 Django 直接服务，前端直接拼接为完整 URL 即可显示：

```html
<img src="/media/avatars/photo.jpg" />
```

如果前端使用独立 dev server，需代理 `/media` 到后端。

## 用户引用与头像渲染

任务、消息等接口中所有「用户」字段（创建人、负责人、协作者、认领人、审批人、附件上传者、消息发送者、会话参与者）都使用统一的精简用户结构 `SimpleUserSerializer`：

```json
{
  "id": 2,
  "username": "test",
  "email": "test@example.com",
  "nickname": "测试员",
  "avatar": "/media/avatars/photo.jpg"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | number | 用户 ID |
| `username` | string | 登录名，始终存在 |
| `email` | string | 邮箱 |
| `nickname` | string | 网名，可能为空字符串 `""` |
| `avatar` | string \| null | 头像相对 URL（`/media/...`，见上方「用户上传文件」）；未上传时为 `null` |

> 这些字段在响应中已统一填充（后端已对用户档案做 `select_related` / `prefetch_related`），前端无需为每个头像再发一次请求。

### 头像渲染约定

显示用户时遵循以下规则（与参考实现 `frontend/src/components/Avatar.tsx` 一致）：

- **显示名**：`nickname || username`（`nickname` 为空时回退到 `username`）。
- **头像**：
  - `avatar` 非空 → 渲染 `<img src={avatar}>`（相对路径，直接挂在站点根下）。
  - `avatar` 为 `null` → 渲染**默认头像**：圆形底色 + 显示名的首字符（英文取首字母并大写，中日韩等取第一个字）。

参考组件契约（任意技术栈均可复刻）：

```ts
type AvatarUser = { avatar: string | null; nickname?: string; username: string };
// props: { user: AvatarUser; size?: "sm" | "md" }
//   sm = 24px（列表、行内 meta）  md = 32px（评论、会话头部）
const displayName = user.nickname || user.username || "?";
const initial = displayName.charAt(0).toUpperCase();
```

行内「头像 + 用户名」建议用同一段水平布局（参考实现中对应 `.user-with-avatar`：flex、垂直居中、间距 6px）。

### 应渲染头像的位置

为保证体验一致，移植前端时应在以下位置渲染头像（`avatar` 为 `null` 时用默认头像）：

| 位置 | 来源字段 | 尺寸 |
|------|----------|------|
| 任务详情·创建人 / 负责人 / 协作者 | `creator` / `assignee` / `collaborators[]` | sm |
| 任务详情·讨论（评论） | 每条消息的 `sender` | md |
| 任务详情·认领请求 | `claim_requests[].claimant` | sm |
| 任务列表 / 时间线·负责人 | `assignee` | sm |
| 站内消息·私人会话头部（显示对方） | 对方参与者 | md |
| 站内消息·气泡作者（仅对方消息） | `sender` | sm |
| 任务表单·协作者选择器 | 候选用户列表 | sm |

注意事项：

- 负责人 / 认领人可能为空（未分配、无认领请求），此时**不渲染**头像，只显示「未分配」等占位文本。
- 站内消息中**自己的消息不显示**作者头像（仅对方消息显示）。
- 任务会话（多人）头部不绑定单个用户，不显示头像；只有私人会话头部显示对方头像。
- 原生 `<select>` 的 `<option>` 无法渲染图片，因此任务表单的「负责人」下拉**不**带头像（协作者改用按钮形式，可带头像）。

## 任务系统

任务系统是本项目核心。任何登录用户可查看/创建任务；编辑、指派、审批等操作按角色与状态受限（见「权限模型」）。任务可携带标签、协作者、附件，并内置「认领」与「验收」两套独立审批流。

### 数据模型

**任务** 详情接口返回完整对象，列表接口返回精简对象（无 `description` / `attachments` / `claim_requests`，多一个 `attachment_count`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | number | |
| `title` | string | 标题 |
| `description` | string | 描述（富文本 HTML，仅详情） |
| `status` | enum | 任务状态，见下 |
| `priority` | enum | 优先级，见下 |
| `creator` | User | 创建人（只读，= 当前用户） |
| `assignee` | User \| null | 负责人 |
| `collaborators` | User[] | 协作者（仅详情） |
| `tags` | Tag[] | 标签 |
| `attachments` | Attachment[] | 附件（仅详情） |
| `claim_requests` | ClaimRequest[] | 认领请求（仅详情） |
| `attachment_count` | number | 附件数（仅列表） |
| `completed_at` | string \| null | 完成时间 |
| `reject_reason` | string | 打回理由（空串=无） |
| `created_at` / `updated_at` | string | |

**标签**：`{id, name, color, task_count}`，`color` 为 `#rrggbb`。
**附件**：`{id, file_url, file_type, file_name, file_size, uploaded_by, uploaded_at}`，`file_url` 为**绝对** URL（含域名，与相对的 `avatar` 不同）。
**认领请求**：`{id, task, claimant, status, reason, reviewed_by, reviewed_at, created_at}`。

### 枚举与配色

任务状态 `status`（前端配色）：

| 值 | 中文 | 色值 |
|----|------|------|
| `pending` | 待处理 | `#6b7280` |
| `in_progress` | 进行中 | `#3b82f6` |
| `reviewing` | 待验收 | `#8b5cf6` |
| `review` | 审核中 | `#f59e0b` |
| `completed` | 已完成 | `#10b981` |
| `cancelled` | 已取消 | `#9ca3af` |

优先级 `priority`：`low` 低 `#6b7280` / `medium` 中 `#3b82f6` / `high` 高 `#f59e0b` / `urgent` 紧急 `#ef4444`。
认领状态 `claim.status`：`pending` 待审核 / `approved` 已通过 / `rejected` 已拒绝。
附件类型 `file_type`：`image` / `video` / `document` / `archive` / `other`。

### 任务接口

前缀 `/tasks/tasks/`（DRF Router，标准 REST + 自定义 action）。

| 接口 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/tasks/tasks/` | GET | 登录 | 列表（支持过滤/搜索/排序） |
| `/tasks/tasks/` | POST | 登录 | 创建（`creator` 自动=当前用户） |
| `/tasks/tasks/{id}/` | GET | 登录 | 详情 |
| `/tasks/tasks/{id}/` | PUT/PATCH | 创建人或社长（仅 `pending`） | 编辑 |
| `/tasks/tasks/{id}/` | DELETE | 创建人或社长（仅 `pending`） | 删除 |
| `/tasks/tasks/my_tasks/` | GET | 登录 | 我相关的任务（创建/负责/协作） |

**创建/编辑请求体**（JSON，`status` 不可直接写）：

```json
{
  "title": "任务标题",
  "description": "<p>富文本 HTML</p>",
  "priority": "medium",
  "assignee_id": 3,
  "collaborator_ids": [2, 5],
  "tag_ids": [1]
}
```

- 用 `assignee_id` / `collaborator_ids` / `tag_ids` 传 ID。
- 创建时：带 `assignee_id` → 直接 `in_progress`；否则 `pending`。

**任务动作**（`POST /tasks/tasks/{id}/<action>/`，返回最新任务详情）：

| 动作 | 前置状态 | 操作人 | 入参 / 说明 |
|------|----------|--------|-------------|
| `claim` | 无负责人 且 `pending`/`review` | 任意登录 | body `reason`；首个申请将 `pending`→`review` |
| `approve_claim` | — | 创建人或社长 | body `claim_id`；负责人=申请者，`→in_progress` |
| `reject_claim` | — | 创建人或社长 | body `claim_id`；无待审申请则 `review`→`pending` |
| `complete` | `in_progress` | 负责人或社长 | 提交验收，`→reviewing`，清空 `reject_reason` |
| `approve_completion` | `reviewing` | 创建人或社长 | `→completed`，写 `completed_at` |
| `reject_completion` | `reviewing` | 创建人或社长 | body `reason`（必填）；`→in_progress`，写 `reject_reason` |
| `cancel` | 非 `completed` | 创建人或社长 | `→cancelled` |
| `assign` | — | **社长** | body `assignee_id`（空=取消指派）；`→in_progress`/`pending` |
| `add_attachment` | 见权限模型 | 见权限模型 | `multipart`，字段 `file`；≤50MB，禁 `.exe/.bat/.sh/.py` 等 |
| `delete_attachment` | — | 上传者/创建人/社长 | body `attachment_id` |

### 任务状态流转

- `pending` 待处理：初始（无负责人）。可 `claim`→`review`，或被社长 `assign`→`in_progress`。
- `review` 审核中：有人申请认领、等待审批。`approve_claim`→`in_progress`；`reject_claim` 且无其它待审申请→`pending`。
- `in_progress` 进行中：已有负责人。`complete`→`reviewing`；验收被打回会回到此状态（带 `reject_reason`）。
- `reviewing` 待验收：负责人已提交、等待验收。`approve_completion`→`completed`；`reject_completion`（写 `reject_reason`）→`in_progress`。
- `completed` 已完成：终态。
- `cancelled` 已取消：可由任意非完成态 `cancel` 进入。

> ⚠️ `review`（审核中 = 认领审批）与 `reviewing`（待验收 = 工作验收）是两条独立审批线，命名相近、语义不同，移植时务必区分。验收被打回后重新 `complete` 会清空 `reject_reason`，前端应在详情页据此提示「被打回」。

### 权限模型

- **社长**：用户组「社长」成员，拥有任务系统全部管理权限（指派、审批、编辑标签、删任意附件等）。
- **任意登录用户**：查看所有任务、创建任务、申请认领、在自己参与的会话中发消息。
- **任务编辑/删除**：仅当 `pending`，且为创建人或社长。
- **认领审批 / 验收 / 取消**：创建人或社长。
- **直接指派 `assign`**：仅社长。
- **附件上传**：`in_progress` 前仅创建者；`in_progress` 期间创建者/负责人/协作者；社长始终。
- **附件删除**：上传者、创建人或社长。
- **标签写**：仅社长（读：任意登录用户）。
- **消息**：仅会话参与者。

> `/auth/me/` 返回 `user.is_president`（布尔），前端可据此预判当前用户是否为社长、显示对应操作 UI（审批 / 验收 / 取消等）。实际操作仍由后端校验、失败返回 403，前端应同时兜底。注意：该字段只在当前用户接口出现，任务 / 消息里引用的**其他**用户（`SimpleUserSerializer`）不含此字段。

### 标签接口 `/tasks/tags/`

标准 REST：GET 列表/详情（任意登录）；POST/PUT/PATCH/DELETE（仅社长）。`search_fields=["name"]`。

### 附件接口 `/tasks/attachments/`

只读（GET 列表/详情），`filterset_fields=["task","file_type"]`。上传/删除请走任务详情的 `add_attachment` / `delete_attachment` 动作。

## 站内消息与任务讨论

消息系统统一用「会话 Conversation」承载，分两类：

- `task` 任务讨论：绑定一个任务，参与者由后端自动补齐（创建人 + 负责人 + 协作者 + 社长 + 请求者）。
- `private` 私人对话：两个用户之间。

前缀 `/messaging/conversations/`。

### 会话与消息结构

**会话**：`{id, conversation_type, task, title, participants[], last_message, unread_count, created_at, updated_at}`。
**消息**：`{id, conversation, sender, content, mentions[], is_read, created_at, updated_at}`。

`last_message` / `unread_count` / `is_read` 均相对当前用户计算。

### 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/messaging/conversations/` | GET | 我的会话列表（按 `updated_at` 倒序）；可过滤 `?conversation_type=private`、`?task=<id>` |
| `/messaging/conversations/{id}/` | GET | 会话详情（仅参与者） |
| `/messaging/conversations/{id}/send_message/` | POST | 发送消息；body `content`；正文 `@用户名` 自动解析为 `mentions` |
| `/messaging/conversations/{id}/mark_read/` | POST | 标记该会话所有消息为已读 |
| `/messaging/conversations/messages/?conversation_id=X` | GET | 拉取某会话的消息列表 |
| `/messaging/conversations/start_private/` | POST | 发起/复用私人会话；body `user_id`（不能是自己） |
| `/messaging/conversations/get_task_conversation/` | POST | 获取/创建任务讨论会话；body `task_id`（需有任务访问权） |

要点：

- 任务讨论入口：打开任务详情「讨论」时调 `get_task_conversation`，后端自动建会话并补齐参与者。
- 进入会话后应调 `mark_read` 把 `unread_count` 清零。
- 权限：仅会话参与者可读/发消息。

## URL 路由约定

Django 的路由规则：

| 路径 | 处理方 |
|------|--------|
| `/admin/*` | Django Admin |
| `/auth/*` | Django API（账号/资料/用户） |
| `/tasks/*` | Django API（任务/标签/附件） |
| `/messaging/*` | Django API（消息/讨论） |
| `/static/*` | 静态文件 |
| `/media/*` | 用户上传文件 |
| 其他所有路径 | 返回 `index.html`（SPA） |

前端路由不受限制，Django 会将所有非后端路径交给前端处理。路径选择只需避开 `/admin/`、`/auth/`、`/tasks/`、`/messaging/`、`/static/`、`/media/` 即可。

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
