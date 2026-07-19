# 角色 → 权限迁移设计

日期：2026-07-19 · 作者：与 jinha 协作

## 目标与动机

现状用「组名硬编码」做鉴权：`is_president(user)` = `user.groups.filter(name="社长")`，
`is_info_group(user)` = `... name="信息组"`。能力被写死在代码里、绑死在组名上，
无法在不改代码的前提下授予/收回单项能力。

目标（用户原话）：

> 移除信息组和社长的设定，全部改为对应的权限，然后用组管理；信息组是一个默认组，社长也是一个默认组。

即：**鉴权改用 Django `Permission`（`has_perm`）**；**信息组 / 社长 作为默认组保留**，
作为「权限束」供组管理（Django admin）分配成员。已确认两项决策：

1. **混合权限粒度**：CRUD 用 Django 自动模型权限；工作流动作用自定义权限。
2. **前端能力布尔**：`/auth/me/` 返回语义化 `can_*` 字典，前端不耦合权限代号。

## 两层模型（厘清「权限类是否还像之前」）

| 层 | 是什么 | 本次变化 |
|---|---|---|
| **能力层**（`Permission` + `Group`，DB） | WHAT：用户能做什么 | **新增**——之前不存在真实 Permission；现在建权限行 + 两个默认组并按组授予 |
| **执行层**（DRF `BasePermission` 子类） | HOW：API 如何校验请求 | **保留形状**，但内核由「查组名」改为 `has_perm`；纯 CRUD 视图直接换 DRF 内置权限后端，不再手写类 |

## 权限集与组分配

自定义权限（写入模型 `Meta.permissions`）：

- `tasks.Task`：`("manage_tasks", "可管理/审批任意任务")`、`("assign_task", "可直接指派任务")`
- `tasks.Tag`：`("manage_tags", "可管理标签")`
- `proposals.Proposal`：`("approve_proposal", "可审批申报")`、`("view_feedback", "可查看意见反馈/举报")`

Django 自动模型权限（无需声明）：`news.add_news` / `news.change_news` / `news.delete_news`、
`proposals.change_proposal`、`tasks.*`、`proposals.*` 的 add/change/delete/view。

默认组分配：

| 组 | 被授予的权限 |
|---|---|
| **信息组** | `news.add_news`、`news.change_news`、`news.delete_news` |
| **社长** | `tasks.manage_tasks`、`tasks.assign_task`、`tasks.manage_tags`、`proposals.approve_proposal`、`proposals.view_feedback`、`proposals.change_proposal` |

超管（`is_superuser`）`has_perm` 恒真 → 自动拥有全部能力，无需特判。

## 数据迁移

模型 `Meta` 改动 → `makemigrations` 生成各 app 的 `AlterModelOptions` 迁移（tasks、proposals）。

新增数据迁移 `accounts/migrations/0004_seed_default_groups.py`（幂等 `RunPython`）：

- 依赖 `accounts.0003_usersession`、`news.0002_create_info_group`、tasks/proposals 的最新迁移；
- `Group.objects.get_or_create` 确保 **信息组** 与 **社长**；
- 把上表权限集按代号查 `Permission` 后 `group.permissions.add(...)`（幂等）。

> **已知陷阱**：Meta 自定义权限由 `post_migrate` 信号在**全部迁移跑完后**才创建，
> 数据迁移**执行期间**尚未存在，`Permission.objects.get(...)` 会 `DoesNotExist`。
> 处理：迁移内先强制 `create_permissions(app_config, apps=apps, verbosity=0)`（对所有相关 app），
> 再查权限；或对每个权限显式 `get_or_create(content_type=..., codename=..., defaults={name})`。
> `reverse_code = migrations.RunPython.noop`（不删组/不撤权，避免误伤成员）。

存量用户：已在「信息组」/「社长」组的用户，迁移后**自动**继承新权限（Django 组→权限），
无需改用户数据。

## 后端执行层改动（`has_perm` 取代 helper）

| 文件 | 现状 | 改为 |
|---|---|---|
| `news/permissions.py` | `CanManageNews` = 信息组 or superuser | **删除整个类**与 `INFO_GROUP`/`is_info_group`；视图改用 DRF 内置 `DjangoModelPermissionsOrAnonReadOnly`（见下） |
| `news/views.py` | `get_permissions()` 按 PUBLIC_ACTIONS 分支 AllowAny / IsAuthenticated+CanManageNews | 简化为：全部 action 返回 `[DjangoModelPermissionsOrAnonReadOnly()]`——GET（list/retrieve/featured/hot/tags）匿名可读，POST/PUT/PATCH/DELETE（create/update/destroy/upload_image）按模型权限校验（`news.add_news`/`change_news`/`delete_news`） |
| `tasks/permissions.py` | `is_president` + `PRESIDENT_GROUP` + 各自定义类 | 删 `is_president`/`PRESIDENT_GROUP`；`CanModifyTask` 对象级→`creator==user or has_perm("tasks.manage_tasks")`；`CanAssignTask`→`has_perm("tasks.assign_task")`；`CanUploadAttachment`/删除附件 override→`has_perm("tasks.manage_tasks")`；`CanManageTag` 写→`has_perm("tasks.manage_tags")` |
| `tasks/views.py`（8 处内联 `is_president`） | 认领审批、提交/通过/打回验收、取消、删除附件 | 每处 `is_president(request.user)` → `request.user.has_perm("tasks.manage_tasks")` |
| `proposals/permissions.py` | `from tasks.permissions import is_president` | 移除导入；`CanViewProposal` 对象级反馈→`has_perm("proposals.view_feedback")`；`CanModifyProposal`→`creator==user or has_perm("proposals.change_proposal")`；`CanApproveProposal`→`has_perm("proposals.approve_proposal")`；`CanManageProposalAttachment` override→`has_perm("proposals.change_proposal")` |
| `proposals/views.py` | `get_queryset` 反馈过滤（108）、删除附件 override（313） | 反馈→`has_perm("proposals.view_feedback")`；删附件→`has_perm("proposals.change_proposal")` |
| `proposals/notifications.py` | `_presidents()` 按组名 `PRESIDENT_GROUP` 查 | 重命名 `_proposal_approvers()`：按 `groups__permissions__codename="approve_proposal"` 查可审批者（含直接授予权限者，更正确）；移除 `PRESIDENT_GROUP` 导入 |

## API 契约（能力布尔，干净切换）

`accounts/views.py` 的 `_profile_response`：**移除** `is_president`/`is_info_group`，新增 `permissions`：

```jsonc
"user": {
  "id": 1, "username": "...", "email": "...",
  "permissions": {
    "can_manage_news":       false,
    "can_manage_tasks":      true,
    "can_assign_task":       true,
    "can_manage_tags":       true,
    "can_approve_proposals": true,
    "can_change_proposals":  true,
    "can_view_feedback":     true
  }
}
```

七个能力。`can_change_proposals`（`proposals.change_proposal`）覆盖「社长可改任意已打回申报 / 管理任意申报附件」——`ProposalDetailPage` 的编辑/重提/附件按钮需要它（与 `can_approve_proposals` 是不同权限）。

能力由一个 `_capabilities(user)` helper 计算（`user.has_perm(...)`）。单一代码库，干净切换，不保留旧字段别名。
`is_president`/`is_info_group` 的导入从 `accounts/views.py` 移除。

## 前端改动（按真实能力替换布尔）

| 文件 | 现状 | 改为 |
|---|---|---|
| `components/AppShell.tsx` | `AppShellUser` 声明 `is_president`/`is_info_group`，**但从未使用**（NAV/USER_MENU 静态） | 直接从接口删两个字段（死代码清理），不引入能力门禁 |
| `pages/NewsListPage.tsx` | `interface Me { is_info_group }`；`me?.is_info_group` 显「写新闻」 | `permissions.can_manage_news` |
| `pages/NewsFormPage.tsx` | `setAllowed(!!d.user?.is_info_group)` | `!!d.user?.permissions?.can_manage_news` |
| `pages/ProposalListPage.tsx` | `interface CurrentUser { is_president }`；反馈 tab | `permissions.can_view_feedback` |
| `pages/ProposalDetailPage.tsx` | `isPresident` 同时驱动审批/编辑/附件/看反馈 | 按用途拆：`can_approve_proposals`（审批）、`can_change_proposals`（编辑/重提/附件）、`can_view_feedback`（反馈详情） |
| `pages/TaskDetailPage.tsx` | `currentUser.is_president` 驱动流转动作 | `permissions.can_manage_tasks`（指派按钮→`can_assign_task`） |

各页 `api.me().then` 的解构随之改为读 `d.user.permissions.can_*`（局部 `interface User`/`CurrentUser` 同步更新）。

## 测试与清理

- `tasks/tests.py`（`make_president` helper 加社长组）、`accounts/tests.py`、`news` 测试：
  加组后 **必须重新取用户**刷新权限缓存（`user = User.objects.get(pk=user.pk)`，Django `has_perm` 缓存陷阱）；
  断言改为 `user.has_perm(...)` 或保持行为断言（端到端 API 仍 200/403）。
- 删除全部 `is_president`/`is_info_group`/`INFO_GROUP`/`PRESIDENT_GROUP` 定义与导入。
- UI 文案（「账户由信息组统一分发」「社长最终决定」「本内容由信息组发布」等）是**描述性文字、非鉴权**，保持不动。

## 不在本轮范围

- 不做应用内「组管理」界面——「用组管理」即 Django admin 管理组成员。
- 不新增这两个之外的组/角色。
- 不改变鉴权以外的业务逻辑（状态机、通知文案、对象级 creator 规则均原样保留）。

## 风险 / 注意

1. **迁移期自定义权限不存在**（见「数据迁移」陷阱段）——必须在数据迁移内强制 `create_permissions` 或显式 `get_or_create`。
2. **`has_perm` 缓存**：测试与任何「运行时改组/改权限」场景须重新取用户。
3. **`DjangoModelPermissionsOrAnonReadOnly` 需视图可解析模型**：`NewsViewSet` 经 `get_queryset().model` 可解析到 `News`，符合；其自定义 action（upload_image 为 POST→`add_news`、featured/hot/tags 为 GET→匿名可读）与现有 PUBLIC_ACTIONS 语义一致。
4. **干净切换**：`is_president`/`is_info_group` 从 API 移除后，前端 6 处必须同步改，否则 `undefined`（门禁关闭，安全方向）。

## 验证

- `uv run python manage.py makemigrations` → 生成 tasks/proposals 的 `AlterModelOptions` + accounts 的 seed 迁移。
- `uv run python manage.py migrate` → 无错；shell 验证：信息组成员 `has_perm('news.add_news')==True`、社长 `has_perm('tasks.manage_tasks')==True` 且 `has_perm('news.add_news')==False`、超管全 True。
- `uv run python manage.py test` → 全绿。
- `cd frontend && npm run build` → EXIT 0。
- Playwright 关键流：信息组写新闻 OK / 普通用户写新闻被挡；社长审批申报、任务流转、看反馈 OK；普通用户不可见反馈 tab、不可审批。
