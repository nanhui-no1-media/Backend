# 任务系统评论 — 用户头像与网名 设计文档

- 日期: 2026-07-04
- 状态: 已批准（待 spec review）

## 背景

任务详情页的「讨论」区是任务的评论入口，底层使用 `messaging` 应用的 `Message` 模型（项目里没有独立 Comment 模型）。后端 `SimpleUserSerializer` 已为所有用户引用（`creator` / `assignee` / `collaborators` / `claimant` / `sender` / `mentions` 等）返回 `nickname` 与 `avatar` 字段；前端 `TaskUser` 类型也已包含这两个字段，且各处已显示 `nickname || username`。

**唯一缺口**：头像（avatar）在前端从未被渲染。本次在任务系统 + 站内信所有显示用户名处补上头像，并顺手修复因渲染头像而暴露的 profile N+1 查询。

## 目标 / 非目标

**目标**
- 新建可复用的 `<Avatar>` 组件，统一「有头像显示图片 / 无头像显示首字母渐变圆」的回退逻辑与样式。
- 在任务系统与站内信所有显示用户名的位置渲染头像。
- 修复后端 queryset 的 profile N+1。

**非目标**
- 不改动用户资料上传（ProfilePage）与导航栏头像（HomePage）——已有实现，避免顺手重构引入回归。
- 不新增后端字段 / 迁移 / 序列化器。
- 不在 `<select><option>` 下拉项中放头像（浏览器不支持 `<option>` 内嵌图片）。

## 方案

采用共享 `<Avatar>` 组件（方案 A），而非每处内联同一段 JSX（方案 B，易漂移）或头像+名字捆绑的 `<UserChip>`（方案 C，对评论/meta 等需分离摆放的布局太死板）。

### 组件设计：`frontend/src/components/Avatar.tsx` + `Avatar.css`

```
Props:
  user: { avatar: string | null; nickname?: string; username: string }
  size?: "sm" | "md"      // 默认 "sm"
  className?: string

渲染（inline-flex 圆形容器）:
  有 avatar → <img src={avatar} alt="" />
  否则      → (nickname || username).charAt(0).toUpperCase()
```

- 视觉复用现有 `.user-avatar`（HomePage 已验证）：圆形、渐变背景、`object-fit: cover`、`overflow: hidden`。
- 尺寸：`sm` = 24px（列表行 / meta / chip），`md` = 32px（讨论评论 / 私聊气泡）。

### 调用点替换

| 文件:行 | 位置 | 处理 |
|---|---|---|
| `TaskDetailPage.tsx:474` | 讨论评论作者（即「评论」） | `<Avatar size="md">` + 名字 |
| `TaskDetailPage.tsx:281` | 创建人 meta | `<Avatar size="sm">` + 名字 |
| `TaskDetailPage.tsx:285` | 负责人 meta | `<Avatar size="sm">` + 名字 |
| `TaskDetailPage.tsx:359` | 协作人 chip | chip 内加 `<Avatar size="sm">` |
| `TaskDetailPage.tsx:401` | 认领申请人 | `<Avatar size="sm">` + 名字 |
| `TaskListPage.tsx:164` | 列表行负责人 | 行内 `<Avatar size="sm">` |
| `TaskTimeline.tsx:80` | 时间线负责人 | 行内 `<Avatar size="sm">` |
| `TaskFormPage.tsx:200` | 已选协作人 chip | chip 内加 `<Avatar size="sm">` |
| `TaskFormPage.tsx:168` | 负责人 `<option>` 下拉项 | **跳过**（HTML 限制） |
| `MessagePage.tsx:135` | 私聊气泡作者 | `<Avatar size="md">` |
| `MessagePage.tsx:72` | 会话标题（对方名字） | 行内 `<Avatar size="sm">` |

### 后端 N+1 修复（无新字段 / 无迁移 / 无序列化器改动）

`SimpleUserSerializer.get_avatar` 访问 `obj.profile`，头像要在列表/详情里大量渲染，需把 profile 预取：

- `tasks/views.py` `TaskViewSet.queryset`（L42-44）：`select_related` 增加 `creator__profile`、`assignee__profile`；`prefetch_related` 增加 `collaborators__profile`、`claim_requests__claimant__profile`。
- `messaging/views.py` `messages` action（L75）：`select_related("sender")` → `select_related("sender", "sender__profile")`。
- `messaging/views.py` `get_queryset`（L28）：prefetch 增加 `messages__sender__profile`。

## 测试 / 验证

- 后端：`uv run python manage.py test tasks messaging`；`uv run python manage.py check`。
- 前端：`cd frontend && npm run build`。
- 手动：有头像用户显示图片、无头像显示首字母；讨论区 / 列表 / 详情 / 私聊均正常。

## 风险

- `<Avatar>` 落地各处时局部布局（flex 对齐、行高）可能需微调对应页面 CSS——实现时逐处确认。
- `select_related("...__profile")` 对没有 profile 行的用户：`SimpleUserSerializer.get_avatar` 已用 `getattr(obj, "profile", None)` 防御，不会报错。
