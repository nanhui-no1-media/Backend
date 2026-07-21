# 个人中心重构设计（Profile Center Refactor）

> 日期：2026-07-21
> 参考：HamCQ 社区个人主页（`https://forum.hamcq.cn/u/<id>`，Flarum）+ 本地 `profile.html`
> 范围档位：**布局重构 + 加「我的内容」tab**，并新增「别人主页」与「权限展示」

## 1. 背景与目标

当前个人中心（`frontend/src/pages/ProfilePage.tsx`）是一整页表单：头像上传、用户名/邮箱（只读）、昵称/生日/性别/简介（行内编辑）、改密码（折叠）、登录记录——全挤在一页，无分区、无内容聚合。

参考 HamCQ 的「Hero 卡片 + 左侧 tab 导航 + 右侧内容区」三段式，把个人中心重构为分层视图，同时新增两个能力：

1. **别人可点头像进入 ta 的主页**（访客视角，看有限信息）
2. **权限展示**：展示该账号的 7 项能力 + 所属组（自己看自己；管理员可看任何人）

## 2. 范围

**做：**
- 三段式布局重构（Hero / 左侧 nav / 右侧内容区），cobalt 风格落地
- 自看自己：7 个 tab（资料编辑 / 改密码 / 登录记录 / 我的新闻 / 我的申报 / 我的任务 / 我的权限）
- 别人看 ta：2 个 tab（ta 的新闻 / ta 的申报），Hero 承载身份信息
- 管理员看别人：额外 1 个权限 tab
- 两个新后端端点（profile / content），可见性服务端强制
- 点头像 → `/u/<id>` 跳转

**不做（YAGNI）：** 封面图自定义上传（先用纯色/渐变）、内容列表分页、列表页按作者过滤、访问量/最近访客统计、HamCQ 的 HAM 专属功能（QSL/通联日志/奖状/呼号/CQ币/Karma/设备库）。

## 3. 路由与身份判定

### 路由（`frontend/src/App.tsx`）
- **新增** `/u/:id` → 懒加载 `UserProfile`（个人主页主路由，`:id` = 用户 pk）
- **改动** `/profile` → `ProfileRedirect`（取 `me.id` 后跳 `/u/<me.id>`，保留该路由因顶栏菜单/页脚均指向 `/profile`）
- **删除** 旧 `ProfilePage` 路由（其内容拆进 panel 子组件）
- tab 状态走 `?tab=<key>` 查询参数（`useSearchParams`）→ 可深链、可分享、浏览器返回键正常

### 身份判定（服务端为准）
接口返回 `viewer: { is_owner, is_admin }`，前端据此渲染，**不自行比对 id**：
- `is_owner`：请求者 = 被查看者
- `is_admin`：请求者是超管 **或** 信息组成员
- 否则为访客（普通成员看别人）

> 隐私前提：本门户账户由信息组统一分发，**访客视角仅对已登录成员开放**；游客命中 `/u/:id` → 接口 401 → `openLogin()`（沿用现有模式）。

### 默认 tab
- 自己 → `news`（我的新闻）
- 别人 → `news`（ta 的新闻）
- 内容优先（与 HamCQ 一致），Hero 已承载身份信息。

## 4. Tab 矩阵（谁看得到哪个 tab）

| Tab key | 标签 | 自己 | 别人(普通) | 别人(管理员) |
|---|---|:---:|:---:|:---:|
| `news` | 我的/ta的 新闻 | ✅ 全部（含草稿） | ✅ 仅已发布 | ✅ 仅已发布 |
| `proposals` | 我的/ta的 申报 | ✅ 全部 | ✅ 仅**已通过** | ✅ 仅已通过 |
| `tasks` | 我的任务（assignee=我） | ✅ | — | — |
| `profile` | 资料编辑 | ✅ | — | — |
| `password` | 改密码 | ✅ | — | — |
| `sessions` | 登录记录 | ✅ | — | — |
| `permissions` | 权限（7 项能力 + 组） | ✅ | — | ✅ |

**要点：**
- 别人的身份信息（头像/昵称/角色徽章/简介/注册时间）全在 Hero，**别人不需要单独的「资料」tab**。
- 别人看申报只露出 `status=approved`（公开记录）；草稿/被拒/撤回/打回对他人不可见。
- 任务对他人完全不可见（接口直接 403，不是返空）。
- email / birthday / gender 仅自己可见。

## 5. 布局与视觉

三段式，套在现有 `<AppShell>` 内（cobalt 风格）：

```
自己看自己（宽屏）：
┌───────────────────────────────────────────────────┐
│ ▓▓▓ 封面色块 / brand 渐变 ▓▓▓                       │  ← Hero 卡片（整宽）
│  ╭────╮                                            │
│  │头像│  用户名  [角色徽章]              [编辑资料] │
│  │ lg │  注册于 … · 角色                             │
│  ╰────╯  个人简介（空则有 placeholder）             │
└───────────────────────────────────────────────────┘
┌──────────────┐ ┌──────────────────────────────────┐
│ ◉ 我的新闻   │ │  我的新闻                          │
│   我的申报   │ │  ┌────────────────────────────┐  │
│   我的任务   │ │  │ 标题 · 分类 · 时间          │  │
│  ─────────  │ │  │ 标题 · 分类 · 时间          │  │
│   资料编辑   │ │  └────────────────────────────┘  │
│   改密码     │ │                                    │
│   登录记录   │ │                                    │
│   我的权限   │ │                                    │
└──────────────┘ └──────────────────────────────────┘
   左 sideNav          右内容区（?tab=）

别人看 ta（tab 少 → 横向 tab 条，不出左栏）：
┌───────────────────────────────────────────────────┐
│ ▓▓▓ 封面色块 ▓▓▓                                   │
│  ╭────╮                                            │
│  │头像│  ta用户名  [角色徽章]                       │
│  ╰────╯  注册于 … · 简介                            │
└───────────────────────────────────────────────────┘
   [ ta的新闻 ]  [ ta的申报 ]  [ 权限 ]*   ← 横向 tab 条（*仅管理员）
┌───────────────────────────────────────────────────┐
│  ta的新闻 ……                                        │
└───────────────────────────────────────────────────┘
```

**自适应：** tab 多（自己，7 个）→ 左侧 sideNav；tab 少（别人，2~3 个）→ Hero 下横向 tab 条。窄屏一律折叠成横向滚动条。

**cobalt 落地：**
- 新建 `frontend/src/styles/profile.css`（随 `UserProfile` chunk 懒加载）
- Hero：brand 渐变封面 + `--surface-1` 卡片 + `--ink-*` 文字；右上「编辑资料」按钮仅 `is_owner` 可见
- 角色徽章：新建**组→色映射**（社长 / 信息组 / 成员），从接口返回的 role 渲染
- 头像沿用现有 `<Avatar>` 组件（留意 `.avatar` 类名碰撞债务，必要时局部高特异性覆盖，参考 `TaskTimeline.css` 做法）
- 新样式类：`.profile-hero` / `.profile-sidenav` / `.profile-tabs` / `.profile-panel`

**组→色映射（`types/profile.ts`）：**
| 组 | 角色 label | 色 |
|---|---|---|
| 社长 | 社长 | amber/gold（如 `--warning`） |
| 信息组 | 信息组 | brand 蓝（`--brand-600`） |
| 其他 | 成员 | 灰（`--ink-400`） |

## 6. 后端 API 契约

全部加在 `accounts` 应用（`accounts/urls.py`），挂在已有 `auth/` 前缀下。
**注意：`config/urls.py` 的 catch-all 正则已排除 `auth/`，无需改动。**

### ① `GET /auth/users/<id>/profile/` — 看个人主页（按身份裁剪）

返回内容随请求者身份变化（**隐私边界服务端强制**）：

| 字段 | 公开 | 自己 | 管理员 |
|---|:---:|:---:|:---:|
| `user.id` / `user.username` / `user.date_joined` | ✅ | ✅ | ✅ |
| `profile.avatar` / `profile.nickname` / `profile.bio` | ✅ | ✅ | ✅ |
| `role`（主角色 `{label, color}`，从组派生） | ✅ | ✅ | ✅ |
| `user.email` / `profile.birthday` / `profile.gender` | — | ✅ | — |
| `permissions`（7 项能力 + `groups` 列表） | — | ✅ | ✅ |
| `viewer`（`is_owner` / `is_admin`） | ✅ | ✅ | ✅ |

- `@login_required`
- 用户不存在/未激活 → 404
- `permissions` 复用 `accounts.views._capabilities(viewed_user)`（对**被查看者**计算）
- 新增辅助 `_role_for(user)`：社长 > 信息组 > 成员，返回 `{label, color}`
- 响应 shape：私有字段**条件包含**（不返 null），前端 TS 类型标记为可选

### ② `GET /auth/users/<id>/content/?type=news|proposals|tasks` — tab 内容（懒加载）

每点一个 tab 单独请求，**可见性服务端兜底**：

| type | 自己 | 别人 | 摘要字段 |
|---|---|---|---|
| `news` | 全部（含草稿） | 仅 `is_published=true` | title / category / cover_image / published_at（或 created_at） |
| `proposals` | 全部 | 仅 `status=approved` | title / proposal_type / status / created_at |
| `tasks` | `assignee=<id>` | **403** | title / status / priority / due（如有） |

- 返回最近 N 条（N=15），按各自模型默认 ordering
- 跨 app 查询：accounts 视图 import `news.models.News` / `proposals.models.Proposal` / `tasks.models.Task`（核心 app 间耦合，可接受）
- 卡片点击跳各自详情页 `/news/:id`、`/activity/:id`、`/tasks/:id`
- `tasks` 对非 owner 直接 403（非空列表）

### 复用现有端点（自看自己的 tab 不变）
- `/auth/me/`（`ProfileRedirect` 取 `me.id`）
- `/auth/profile/update/`（资料编辑 panel）
- `/auth/profile/change-password/`（改密码 panel）
- `/auth/sessions/`（登录记录 panel）

### 前端 `api/client.ts` 增补
```ts
getUserProfile: (id: number) => request(`/users/${id}/profile/`),
getUserContent: (id: number, type: "news" | "proposals" | "tasks") =>
  request(`/users/${id}/content/?type=${type}`),
```

## 7. 前端结构与数据流

### 文件结构（拆子组件，避免单文件膨胀）
```
pages/
  UserProfile.tsx          ← 新主页面（编排：取 profile + 决定 tab 集 + 渲染 Hero/Nav/面板）
  ProfileRedirect.tsx      ← /profile → 取 me.id → 跳 /u/<id>
components/profile/
  ProfileHero.tsx          ← Hero 卡片
  ProfileSideNav.tsx       ← 左侧垂直 nav（自己，7 tab）
  ProfileTabs.tsx          ← 横向 tab 条（别人，2~3 tab）
  ProfileEditPanel.tsx     ← 资料编辑（从现 ProfilePage 表单整体搬过来）
  PasswordPanel.tsx        ← 改密码（搬现成折叠表单）
  SessionsPanel.tsx        ← 登录记录（搬现成会话列表）
  ContentListPanel.tsx     ← 通用内容面板（props.type → getUserContent → 卡片），新闻/申报/任务复用
  PermissionsPanel.tsx     ← 权限（7 项能力 + 所属组，只读）
styles/profile.css         ← 全部 profile 样式
types/profile.ts           ← TS 类型 + 组→色 映射
```

### 数据流
1. 进 `/u/:id?tab=...` → `api.getUserProfile(id)` 拿 profile（含服务端 `viewer`）→ 渲染 Hero
2. 身份判定用服务端 `viewer.is_owner/is_admin`（不靠前端比 id）
3. 当前 tab 读 `useSearchParams().get("tab")`；若不在该身份允许集 → 回退默认 tab
4. tab 面板挂载时各自懒加载：内容面板调 `getUserContent`；编辑/改密/会话面板调各自现有端点
5. 资料保存成功 → 刷新本地 profile + `notifyAuthChange()` 让顶栏头像/昵称同步
6. `ProfileRedirect` 需 `me.id` → 调 `api.me()`；`UserProfile` 本身不需要 me（用服务端 viewer）

### Tab 允许集（前端兜底，镜像服务端规则）
```
自己:         news · proposals · tasks · profile · password · sessions · permissions
别人:         news · proposals
别人+管理员:   news · proposals · permissions
```

### 点头像跳转
渲染头像处（任务负责人、新闻作者、申报创建人、消息列表等）的 `<Avatar>` 包一层链接 → `/u/<id>`。这些位置已能拿到用户 id（`/auth/users/` 列表、各模型 author/creator/assignee 字段）。

## 8. 边界处理
- 用户不存在 / 未激活 → 接口 404 → 页面「用户不存在」空态
- tab 参数非法 / 该身份无权 → 回退默认 tab
- 访客未登录命中 `/u/:id` → 接口 401 → `openLogin()`
- 自己经 `/u/<my-id>` 直达 → 服务端 `is_owner=true`，照常
- 资料保存后 → 刷本地 profile + `notifyAuthChange()` 同步顶栏
- 内容列表空 → 各 tab「暂无内容」占位
- 管理员看别人的权限 tab → 只读展示该账号 7 项能力 + 所属组
- 窄屏 → 左 sideNav 折叠为横向滚动 tab 条

## 9. 测试

**后端（`accounts/tests.py`）：**
- profile 字段按身份裁剪：公开断言无 email/birthday/gender/permissions；自己断言全有；管理员断言有 permissions 无 email
- content 可见性：news 别人只拿到 published；proposals 别人只拿到 approved；tasks 别人 403
- 未知 / 未激活用户 → 404
- `_role_for()` 角色/颜色派生正确（社长/信息组/成员）

**前端：**
- 三种身份的 tab 集渲染正确（自己 7 / 别人 2 / 管理员 3）
- `/profile` → `/u/<id>` 重定向
- 非法 tab 回退默认
- 编辑/改密/会话三块逻辑从旧页搬过来后冒烟通过

## 10. 涉及文件清单

**后端：**
- `accounts/views.py` — 新增 `user_profile_view`、`user_content_view`、`_role_for`；复用 `_capabilities`
- `accounts/urls.py` — 新增 2 条 path
- `accounts/tests.py` — 新增测试
- `config/urls.py` — **不改**（`auth/` 已在 catch-all 排除）

**前端：**
- `frontend/src/App.tsx` — 路由：新增 `/u/:id`，改 `/profile` 为重定向，删旧 ProfilePage 路由
- `frontend/src/pages/UserProfile.tsx`（新）
- `frontend/src/pages/ProfileRedirect.tsx`（新）
- `frontend/src/components/profile/*`（新，8 个组件）
- `frontend/src/styles/profile.css`（新）
- `frontend/src/types/profile.ts`（新）
- `frontend/src/api/client.ts` — 增 2 个方法
- 删除 `frontend/src/pages/ProfilePage.tsx`（内容拆进 panel）
- 各渲染头像处：包 `<Avatar>` 链接到 `/u/<id>`（任务/新闻/申报/消息相关组件）

**数据库迁移：** 无（不新增模型字段，`date_joined`/组关系均已存在）。
