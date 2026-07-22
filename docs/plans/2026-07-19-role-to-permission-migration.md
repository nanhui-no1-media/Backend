# 角色 → 权限迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把所有 `is_president` / `is_info_group` 组名硬编码鉴权改为 Django `Permission`（`has_perm`），信息组 / 社长作为默认组承载权限束，前端经语义化 `permissions.can_*` 能力字典驱动。

**Architecture:** 两层——能力层（`Permission`+`Group`，DB，新增）+ 执行层（DRF 权限类，保留形状、内核换 `has_perm`；纯 CRUD 的 news 改用 DRF 内置 `DjangoModelPermissionsOrAnonReadOnly`）。先「keystone」把两个 helper 重定义为 `has_perm` 包装（最小改动、全量测试即验证整系统已权限化），再逐 app 把调用换成直接 `has_perm` 并清理。

**Tech Stack:** Django 6.0.5（DRF、auth Permission/Group、contenttypes）、React 19+TS。后端测试 `uv run python manage.py test`，前端 `cd frontend && npm run build`。

**Spec:** `docs/superpowers/specs/2026-07-19-role-to-permission-migration-design.md`

**分支约定:** 在 `roles-to-permissions` 分支上做；仅 `git add <显式路径>`；**不碰**工作树无关变更（`media/avatars/*`、`media/task_attachments/*`、`media/news_content_images/`）；每个 task 结尾提交；最终本地合 main、不推 origin。

---

## 文件总览

**后端**
- 改：`tasks/models.py`（Task/Tag `Meta.permissions`）、`proposals/models.py`（Proposal `Meta.permissions`）
- 建：`accounts/migrations/0004_seed_default_groups.py`
- 改：`tasks/permissions.py`、`tasks/views.py`、`news/permissions.py`、`news/views.py`、`proposals/permissions.py`、`proposals/views.py`、`proposals/notifications.py`、`accounts/views.py`
- 测：`tasks/tests.py`、`accounts/tests.py`、新建 `news/tests.py`、新建 `proposals/tests.py`

**前端**
- 改：`components/AppShell.tsx`、`pages/NewsListPage.tsx`、`pages/NewsFormPage.tsx`、`pages/ProposalListPage.tsx`、`pages/ProposalDetailPage.tsx`、`pages/TaskDetailPage.tsx`

---

## Task 1: 建分支、提交 spec 与 plan

**Files:** 无代码改动。

- [ ] **Step 1: 建分支**

```bash
git checkout -b roles-to-permissions
```

- [ ] **Step 2: 提交 spec + plan（显式路径，不碰无关变更）**

```bash
git add docs/superpowers/specs/2026-07-19-role-to-permission-migration-design.md docs/superpowers/plans/2026-07-19-role-to-permission-migration.md
git commit -m "$(cat <<'EOF'
docs(perm): 角色→权限迁移的 spec 与实现计划

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 模型自定义权限 + 迁移

**Files:**
- Modify: `tasks/models.py`（`Task.Meta`、`Tag.Meta`）
- Modify: `proposals/models.py`（`Proposal.Meta`）
- Create（makemigrations 生成）: `tasks/migrations/000X_*`、`proposals/migrations/000X_*`

- [ ] **Step 1: `tasks/models.py` `Tag.Meta` 加权限**

把 `Tag.Meta` 改为：

```python
    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"
        ordering = ["name"]
        permissions = [
            ("manage_tags", "可管理标签"),
        ]
```

- [ ] **Step 2: `tasks/models.py` `Task.Meta` 加权限**

把 `Task.Meta` 改为：

```python
    class Meta:
        verbose_name = "任务"
        verbose_name_plural = "任务"
        ordering = ["-created_at"]
        permissions = [
            ("manage_tasks", "可管理/审批任意任务"),
            ("assign_task", "可直接指派任务"),
        ]
```

- [ ] **Step 3: `proposals/models.py` `Proposal.Meta` 加权限**

把 `Proposal.Meta` 改为：

```python
    class Meta:
        verbose_name = "申报"
        verbose_name_plural = "申报"
        ordering = ["-created_at"]
        permissions = [
            ("approve_proposal", "可审批申报"),
            ("view_feedback", "可查看意见反馈/举报"),
        ]
```

- [ ] **Step 4: 生成迁移**

```bash
uv run python manage.py makemigrations tasks proposals
```
预期：`tasks` 生成 1 条 `AlterModelOptions`（Task + Tag），`proposals` 生成 1 条（Proposal）。

- [ ] **Step 5: 应用迁移**

```bash
uv run python manage.py migrate
```

- [ ] **Step 6: 验证权限已生成**

```bash
uv run python manage.py shell -c "from django.contrib.auth.models import Permission as P; print(sorted(p.codename for p in P.objects.filter(content_type__app_label='tasks'))); print(sorted(p.codename for p in P.objects.filter(content_type__app_label='proposals', content_type__model='proposal')))"
```
预期输出包含：tasks → `['add_tag','add_task','add_taskclaimrequest',...,'assign_task','change_tag',...,'manage_tags','manage_tasks',...]`；proposals.proposal → 含 `approve_proposal`、`view_feedback`。

- [ ] **Step 7: 提交**

```bash
git add tasks/models.py proposals/models.py tasks/migrations proposals/migrations
git commit -m "$(cat <<'EOF'
feat(perm): 为 Task/Tag/Proposal 声明自定义权限（manage_tasks/assign_task/manage_tags/approve_proposal/view_feedback）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 默认组 + 赋权数据迁移

**Files:**
- Create: `accounts/migrations/0004_seed_default_groups.py`

- [ ] **Step 1: 写迁移文件**

创建 `accounts/migrations/0004_seed_default_groups.py`：

```python
from django.db import migrations


def seed(apps, schema_editor):
    from django.contrib.auth.management import create_permissions
    from django.contrib.contenttypes.management import create_contenttypes

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # 自定义权限由 post_migrate 在「全部迁移跑完后」才创建；
    # 数据迁移执行期间尚未存在 → 先强制建出 contenttypes 与权限，保证下方能查到。
    for app_config in apps.get_app_configs():
        create_contenttypes(app_config, apps=apps, verbosity=0)
        create_permissions(app_config, apps=apps, verbosity=0)

    GROUP_PERMISSIONS = {
        "信息组": [
            ("news", "add_news"),
            ("news", "change_news"),
            ("news", "delete_news"),
        ],
        "社长": [
            ("tasks", "manage_tasks"),
            ("tasks", "assign_task"),
            ("tasks", "manage_tags"),
            ("proposals", "approve_proposal"),
            ("proposals", "view_feedback"),
            ("proposals", "change_proposal"),
        ],
    }
    for group_name, codenames in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for app_label, codename in codenames:
            perm = Permission.objects.get(
                content_type__app_label=app_label, codename=codename
            )
            group.permissions.add(perm)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_usersession"),
        ("news", "0002_create_info_group"),
        ("tasks", "__last__"),
        ("proposals", "__last__"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
```

> `create_permissions`/`create_contenttypes` 在本机 Django 6.0.5 的签名均为
> `(app_config, verbosity=2, interactive=True, using='default', apps=<...>, **kwargs)`，故传 `apps=apps, verbosity=0`。
> `("tasks", "__last__")` / `("proposals", "__last__")` 由 Django 解析为各 app 最新迁移（即 Task 2 生成的 Meta 迁移）。

- [ ] **Step 2: 应用迁移**

```bash
uv run python manage.py migrate
```
预期：`Applying accounts.0004_seed_default_groups... OK`。

- [ ] **Step 3: 验证两组权限**

```bash
uv run python manage.py shell -c "from django.contrib.auth.models import Group; [print(g.name, sorted('{}.{}'.format(p.content_type__app_label,p.codename) for p in g.permissions.all())) for g in Group.objects.filter(name__in=['信息组','社长'])]"
```
预期：`信息组 ['news.add_news','news.change_news','news.delete_news']`；`社长` 含 `tasks.assign_task/manage_tasks/manage_tags`、`proposals.approve_proposal/change_proposal/view_feedback`。

- [ ] **Step 4: 提交**

```bash
git add accounts/migrations/0004_seed_default_groups.py
git commit -m "$(cat <<'EOF'
feat(perm): 数据迁移——建立信息组/社长默认组并按代号赋权（幂等）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: keystone——把两个 helper 重定义为 has_perm 包装

> 最小改动让**整系统**立即权限化：所有调用 `is_president`/`is_info_group` 的权限类、内联视图、`_profile_response`、`notifications` 一并切换。helper 定义与 `PRESIDENT_GROUP`/`INFO_GROUP` 常量暂时保留，后续 task 再清理。

**Files:**
- Modify: `tasks/permissions.py`（`is_president` 函数体）
- Modify: `news/permissions.py`（`is_info_group` 函数体）

- [ ] **Step 1: 改 `tasks/permissions.py` 的 `is_president`**

```python
def is_president(user: User) -> bool:
    # 角色→权限：社长默认组被授予 tasks.manage_tasks；直接授予该权限亦生效。
    return bool(user and user.is_authenticated and user.has_perm("tasks.manage_tasks"))
```

（`from django.contrib.auth.models import User` 与 `PRESIDENT_GROUP` 常量保留不动；`PRESIDENT_GROUP` 仍被 `proposals/notifications.py` 引用，后续清理。）

- [ ] **Step 2: 改 `news/permissions.py` 的 `is_info_group`**

```python
def is_info_group(user) -> bool:
    # 角色→权限：信息组默认组被授予 news.add_news（及 change/delete）。
    return bool(user and user.is_authenticated and user.has_perm("news.add_news"))
```

（`INFO_GROUP` 常量保留不动，后续清理。）

- [ ] **Step 3: 跑全量测试，确认权限模型端到端成立**

```bash
uv run python manage.py test
```
预期：全绿（`tasks` 测试经 `make_president` 加社长组→因迁移已赋权→`has_perm` 真；`accounts.MeViewTest` 同理）。

> **若 tasks 测试失败（权限缓存）**：`make_president` 在 `user.groups.add` 后若同一实例已被鉴权过，`has_perm` 可能读到旧缓存。修复：在 `tasks/tests.py` 的 `make_president` 末尾加 `user = User.objects.get(pk=user.pk); return user`（强制刷新）。多数情况下 `force_authenticate`/`login` 取的是新实例、首次 `has_perm` 才惰性建缓存，无需刷新——先跑测试，仅在失败时加。

- [ ] **Step 4: 提交**

```bash
git add tasks/permissions.py news/permissions.py
git commit -m "$(cat <<'EOF'
refactor(perm): keystone——is_president/is_info_group 改为 has_perm 包装，整系统权限化

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: News 改用 DRF 内置权限后端，删 CanManageNews

**Files:**
- Modify: `news/views.py`（`get_permissions`、imports）
- Modify: `news/permissions.py`（删 `CanManageNews`；`is_info_group` 包装暂留——`accounts` 仍引用，Task 9 删）
- Create: `news/tests.py`

- [ ] **Step 1: 先写失败测试 `news/tests.py`**

```python
from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import News


def _info(user):
    g, _ = Group.objects.get_or_create(name="信息组")
    user.groups.add(g)
    return user


class NewsPermissionTest(TestCase):
    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.normal = User.objects.create_user(username="normal", password="x")
        self.client = APIClient()
        self.news = News.objects.create(title="t", author=self.author, is_published=True)

    def test_anon_can_read_list(self):
        self.assertEqual(self.client.get("/news/news/").status_code, 200)

    def test_info_group_can_create(self):
        self.client.force_authenticate(self.author)
        resp = self.client.post("/news/news/", {"title": "new"}, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_normal_user_cannot_create(self):
        self.client.force_authenticate(self.normal)
        resp = self.client.post("/news/news/", {"title": "new"}, format="json")
        self.assertEqual(resp.status_code, 403)
```

- [ ] **Step 2: 跑测试，确认失败**

```bash
uv run python manage.py test news
```
预期：当前 `CanManageNews` 仍存在但已走 `is_info_group`（has_perm）——`test_info_group_can_create` 应已通过；若 `CanManageNews` 仍按旧逻辑则失败。无论如何本 task 结束后三项全绿。

- [ ] **Step 3: 改 `news/views.py`**

把 imports 中的：

```python
from rest_framework.permissions import AllowAny, IsAuthenticated
```

改为：

```python
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
```

删除 `from .permissions import CanManageNews`。

把 `get_permissions` 整个方法替换为：

```python
    def get_permissions(self):
        # 公开读（GET：list/retrieve/featured/hot/tags）匿名可读；
        # 写（POST/PUT/PATCH/DELETE：create/update/destroy/upload_image）按 news 模型权限校验。
        return [DjangoModelPermissionsOrAnonReadOnly()]
```

把类 docstring 改为：

```python
    """新闻：公开读（已发布），有 news 写权限者（信息组）可写。"""
```

- [ ] **Step 4: 删 `news/permissions.py` 的 `CanManageNews`**

删除整个 `class CanManageNews(...)`（保留 `INFO_GROUP` 与 `is_info_group`——`accounts` 仍引用，Task 9 删）。

- [ ] **Step 5: 跑测试，确认通过**

```bash
uv run python manage.py test news
```
预期：3 项全绿。

- [ ] **Step 6: 提交**

```bash
git add news/views.py news/permissions.py news/tests.py
git commit -m "$(cat <<'EOF'
refactor(news): 写操作改用 DRF 内置 DjangoModelPermissionsOrAnonReadOnly，删 CanManageNews；补权限测试

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: tasks app——权限类直连 has_perm + 内联视图替换

**Files:**
- Modify: `tasks/permissions.py`（权限类体；**保留** `is_president`/`PRESIDENT_GROUP` 定义）
- Modify: `tasks/views.py`（7 处内联 + import）
- Modify: `tasks/tests.py`（`make_president` docstring）

- [ ] **Step 1: 重写 `tasks/permissions.py` 的权限类（直连 has_perm）**

整文件改为（注意：`is_president`/`PRESIDENT_GROUP` **保留**，因为 `proposals`/`accounts` 仍导入 `is_president`，Task 9 再删）：

```python
from django.contrib.auth.models import User
from rest_framework import permissions

PRESIDENT_GROUP = "社长"


def is_president(user: User) -> bool:
    """[过渡] 等价 has_perm('tasks.manage_tasks')；Task 9 删除。"""
    return bool(user and user.is_authenticated and user.has_perm("tasks.manage_tasks"))


class CanCreateTask(permissions.BasePermission):
    """所有登录用户都可以创建任务"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class CanViewTask(permissions.BasePermission):
    """所有登录用户都能查看所有任务"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return True


class CanModifyTask(permissions.BasePermission):
    """任务编辑/删除：仅 pending 状态可改；进入认领/进行后对所有人锁定（含 manage_tasks 权限者）"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if obj.status != "pending":
            return False
        if request.user.has_perm("tasks.manage_tasks"):
            return True
        return obj.creator == request.user


class CanAssignTask(permissions.BasePermission):
    """直接指派：需 tasks.assign_task 权限（社长默认组授予）"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("tasks.assign_task"))


class CanUploadAttachment(permissions.BasePermission):
    """上传附件：manage_tasks 权限者始终可；否则按创建者/负责人/协作者规则。
    delete_attachment 由视图内逻辑进一步限制（上传者/创建者/manage_tasks 可删）。"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.has_perm("tasks.manage_tasks"):
            return True
        if getattr(view, "action", "") == "delete_attachment":
            return True
        if getattr(view, "action", "") == "add_attachment":
            if obj.status == "in_progress":
                if user == obj.creator or user == obj.assignee:
                    return True
                return obj.collaborators.filter(pk=user.pk).exists()
            return user == obj.creator
        return False


class CanManageTag(permissions.BasePermission):
    """标签管理：所有登录用户可读；写需 tasks.manage_tags 权限"""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return user.has_perm("tasks.manage_tags")
```

- [ ] **Step 2: `tasks/views.py` 去 `is_president` 导入**

把 import 块里的 `is_president,` 行删掉（保留各 Can* 类）：

```python
from .permissions import (
    CanAssignTask,
    CanCreateTask,
    CanManageTag,
    CanModifyTask,
    CanUploadAttachment,
    CanViewTask,
)
```

- [ ] **Step 3: 替换 7 处内联 `is_president(request.user)`**

在 `tasks/views.py` 把每处 `is_president(request.user)`（约 7 处：认领审批/拒绝、提交验收、通过验收、打回、取消、删除附件的 override）替换为：

```python
request.user.has_perm("tasks.manage_tasks")
```

错误消息文案（「只有创建者或社长可以审批」等）保持不动。

- [ ] **Step 4: 更新 `tasks/tests.py` `make_president` docstring**

```python
def make_president(user):
    """把用户加入「社长」组（默认组已被迁移授予 manage_tasks 等权限）。"""
    group, _ = Group.objects.get_or_create(name="社长")
    user.groups.add(group)
    return user
```

- [ ] **Step 5: 跑 tasks 测试**

```bash
uv run python manage.py test tasks
```
预期：全绿（president 经组继承 `manage_tasks`）。

- [ ] **Step 6: 提交**

```bash
git add tasks/permissions.py tasks/views.py tasks/tests.py
git commit -m "$(cat <<'EOF'
refactor(tasks): 权限类与内联视图改用 has_perm 直查（manage_tasks/assign_task/manage_tags）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: proposals app——权限类 + 内联视图 + 通知路由

**Files:**
- Modify: `proposals/permissions.py`
- Modify: `proposals/views.py`（`get_queryset`、`delete_attachment`、import）
- Modify: `proposals/notifications.py`（`_presidents` → `_proposal_approvers`）
- Create: `proposals/tests.py`

- [ ] **Step 1: 先写失败测试 `proposals/tests.py`**

```python
from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Proposal


def _president(user):
    g, _ = Group.objects.get_or_create(name="社长")
    user.groups.add(g)
    return user


class ProposalApprovePermissionTest(TestCase):
    def setUp(self):
        self.normal = User.objects.create_user(username="normal", password="x")
        self.president = _president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        self.prop = Proposal.objects.create(
            proposal_type="activity", status="pending_approval",
            title="p", creator=self.normal,
        )

    def test_non_approver_cannot_approve(self):
        self.client.force_authenticate(self.normal)
        resp = self.client.post(f"/proposals/proposals/{self.prop.pk}/approve/")
        self.assertEqual(resp.status_code, 403)

    def test_approver_can_approve(self):
        self.client.force_authenticate(self.president)
        resp = self.client.post(f"/proposals/proposals/{self.prop.pk}/approve/")
        self.assertEqual(resp.status_code, 200)
```

- [ ] **Step 2: 跑测试确认当前状态**

```bash
uv run python manage.py test proposals
```
（此时 `CanApproveProposal` 仍走 `is_president` 包装=has_perm，应已通过；本 task 把它改成直连并清理。）

- [ ] **Step 3: 重写 `proposals/permissions.py`（直连 has_perm，去 is_president 导入）**

整文件改为：

```python
from rest_framework import permissions


class CanCreateProposal(permissions.BasePermission):
    """所有登录用户都可以创建申报"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanViewProposal(permissions.BasePermission):
    """查看：活动申报所有登录用户可见；意见反馈/举报需 proposals.view_feedback 权限"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.proposal_type == "activity":
            return True
        return request.user.has_perm("proposals.view_feedback")


class CanModifyProposal(permissions.BasePermission):
    """编辑（仅「已打回」）：创建人，或有 proposals.change_proposal 权限者。
    反馈/举报无创建人，打回后由有权限者修订。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.status != "returned":
            return False
        return obj.creator == request.user or request.user.has_perm("proposals.change_proposal")


class CanVoteProposal(permissions.BasePermission):
    """投票：全体成员对「投票中」活动申报可投，每人一次（视图内去重）"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.proposal_type == "activity" and obj.status == "voting"


class CanApproveProposal(permissions.BasePermission):
    """审批（通过/打回/拒绝）：需 proposals.approve_proposal 权限"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("proposals.approve_proposal"))


class CanWithdrawProposal(permissions.BasePermission):
    """撤回：创建人在 投票中/待审批 阶段可撤回"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.status not in ("voting", "pending_approval"):
            return False
        return obj.creator == request.user


class CanManageProposalAttachment(permissions.BasePermission):
    """附件：有 change_proposal 权限者，或申报创建人（已打回可改/补材料）"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.has_perm("proposals.change_proposal"):
            return True
        # 删除接口由视图内部做更细粒度控制（上传者或创建人或有权者）
        if getattr(view, "action", "") == "delete_attachment":
            return True
        return obj.creator == request.user
```

- [ ] **Step 4: `proposals/views.py`——删导入 + 替换 2 处**

删 `from tasks.permissions import is_president`。

`get_queryset` 里：

```python
        # 反馈/举报仅社长可见；其余成员只看得到活动申报
        if not user.is_authenticated or not is_president(user):
            qs = qs.filter(proposal_type="activity")
```

改为：

```python
        # 反馈/举报仅有 view_feedback 权限者可见；其余成员只看得到活动申报
        if not user.is_authenticated or not user.has_perm("proposals.view_feedback"):
            qs = qs.filter(proposal_type="activity")
```

`delete_attachment` 里：

```python
        can_delete = (
            attachment.uploaded_by == request.user
            or is_president(request.user)
            or proposal.creator == request.user
        )
```

改为：

```python
        can_delete = (
            attachment.uploaded_by == request.user
            or request.user.has_perm("proposals.change_proposal")
            or proposal.creator == request.user
        )
```

- [ ] **Step 5: `proposals/notifications.py`——按权限查可审批者**

删 `from tasks.permissions import PRESIDENT_GROUP`。

把 `_presidents` 替换为：

```python
def _proposal_approvers():
    """所有「持有 approve_proposal 权限」的活跃用户（含非社长组直接授权者）。"""
    return list(User.objects.filter(
        is_active=True,
        groups__permissions__codename="approve_proposal",
        groups__permissions__content_type__app_label="proposals",
    ).distinct())
```

`_ensure_conversation` 里 `for p in _presidents():` 改为 `for p in _proposal_approvers():`。模块顶部 docstring 中「全体社长」措辞可保留（描述性）。

- [ ] **Step 6: 跑 proposals 测试**

```bash
uv run python manage.py test proposals
```
预期：2 项全绿。

- [ ] **Step 7: 提交**

```bash
git add proposals/permissions.py proposals/views.py proposals/notifications.py proposals/tests.py
git commit -m "$(cat <<'EOF'
refactor(proposals): 权限类/视图/通知路由改用 has_perm（approve/change/view_feedback）；补审批权限测试

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: accounts API 契约——能力字典

**Files:**
- Modify: `accounts/views.py`（`_capabilities`、`_profile_response`、imports）
- Modify: `accounts/tests.py`（`MeViewTest`）

- [ ] **Step 1: 先改测试（TDD）——`accounts/tests.py` 的 `MeViewTest`**

删除 `test_me_is_president_false_for_normal_user` 与 `test_me_is_president_true_for_president`，替换为：

```python
    def test_me_permissions_all_false_for_normal_user(self):
        self.client.login(username="testuser", password="secret123")
        perms = self.client.get("/auth/me/").json()["user"]["permissions"]
        self.assertFalse(any(perms.values()))

    def test_me_permissions_for_info_group(self):
        from django.contrib.auth.models import Group
        grp, _ = Group.objects.get_or_create(name="信息组")
        self.user.groups.add(grp)
        self.client.login(username="testuser", password="secret123")
        perms = self.client.get("/auth/me/").json()["user"]["permissions"]
        self.assertTrue(perms["can_manage_news"])
        self.assertFalse(perms["can_manage_tasks"])

    def test_me_permissions_for_president(self):
        from django.contrib.auth.models import Group
        grp, _ = Group.objects.get_or_create(name="社长")
        self.user.groups.add(grp)
        self.client.login(username="testuser", password="secret123")
        perms = self.client.get("/auth/me/").json()["user"]["permissions"]
        self.assertTrue(perms["can_manage_tasks"])
        self.assertTrue(perms["can_approve_proposals"])
        self.assertTrue(perms["can_change_proposals"])
        self.assertTrue(perms["can_view_feedback"])
        self.assertFalse(perms["can_manage_news"])
```

- [ ] **Step 2: 跑测试确认失败（旧字段还在）**

```bash
uv run python manage.py test accounts.MeViewTest
```
预期：新测试 KeyError（响应里还没有 `permissions`）。

- [ ] **Step 3: 改 `accounts/views.py`**

删除顶部两行：

```python
from tasks.permissions import is_president
from news.permissions import is_info_group
```

在 `_get_or_create_profile` 之后、`_profile_response` 之前加：

```python
def _capabilities(user):
    """前端能力契约：由 has_perm 派生的语义化布尔（解耦权限代号）。"""
    return {
        "can_manage_news": user.has_perm("news.add_news"),
        "can_manage_tasks": user.has_perm("tasks.manage_tasks"),
        "can_assign_task": user.has_perm("tasks.assign_task"),
        "can_manage_tags": user.has_perm("tasks.manage_tags"),
        "can_approve_proposals": user.has_perm("proposals.approve_proposal"),
        "can_change_proposals": user.has_perm("proposals.change_proposal"),
        "can_view_feedback": user.has_perm("proposals.view_feedback"),
    }
```

把 `_profile_response` 的 `user` 字典改为：

```python
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "permissions": _capabilities(user),
        },
```

（删掉 `is_president`/`is_info_group` 两行；`profile` 字典不动。）

- [ ] **Step 4: 跑 accounts 测试**

```bash
uv run python manage.py test accounts
```
预期：全绿。

- [ ] **Step 5: 提交**

```bash
git add accounts/views.py accounts/tests.py
git commit -m "$(cat <<'EOF'
refactor(auth): /auth/me/ 改返回 permissions 能力字典（7 项 can_*），移除 is_president/is_info_group

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: 后端清理——删除过渡 helper 与常量

**Files:**
- Modify: `tasks/permissions.py`（删 `is_president`、`PRESIDENT_GROUP`、`User` 导入）
- Modify: `news/permissions.py`（删 `is_info_group`、`INFO_GROUP`）

- [ ] **Step 1: 确认无人再引用**

```bash
cd /e/Backend && grep -rn "is_president\|is_info_group\|PRESIDENT_GROUP\|INFO_GROUP" --include="*.py" accounts news tasks proposals config
```
预期：仅 `tasks/permissions.py`（定义）、`news/permissions.py`（定义）命中；`accounts`/`proposals`/`tasks/views.py` 均无引用。（`news/migrations/0002` 有自己的 `INFO_GROUP_NAME`，不算。）

- [ ] **Step 2: 删 `tasks/permissions.py` 顶部**

删除：

```python
from django.contrib.auth.models import User

PRESIDENT_GROUP = "社长"


def is_president(user: User) -> bool:
    """[过渡] 等价 has_perm('tasks.manage_tasks')；Task 9 删除。"""
    return bool(user and user.is_authenticated and user.has_perm("tasks.manage_tasks"))
```

- [ ] **Step 3: 删 `news/permissions.py` 的 `INFO_GROUP` 与 `is_info_group`**

删除：

```python
INFO_GROUP = "信息组"


def is_info_group(user) -> bool:
    ...
```

使文件只剩（若有）其它仍需内容；若 `CanManageNews` 已于 Task 5 删除、文件空，则保留空模块或删除文件并去掉可能引用。检查：`grep -rn "news.permissions" --include="*.py"` 应无命中后，可删整个文件。

- [ ] **Step 4: 全量测试 + check**

```bash
uv run python manage.py check && uv run python manage.py test
```
预期：全绿。

- [ ] **Step 5: 提交**

```bash
git add tasks/permissions.py news/permissions.py
git commit -m "$(cat <<'EOF'
chore(perm): 删除过渡 helper（is_president/is_info_group）与组名常量

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: 前端——AppShell + News

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/pages/NewsListPage.tsx`
- Modify: `frontend/src/pages/NewsFormPage.tsx`

- [ ] **Step 1: `AppShell.tsx` 删死字段**

把 `AppShellUser` 接口改为：

```typescript
interface AppShellUser {
  id: number;
  username: string;
  email: string;
}
```

- [ ] **Step 2: `NewsListPage.tsx`**

```typescript
interface Me { can_manage_news?: boolean }
```

fetch（约 38 行）：

```typescript
    api.me().then((d: any) => setMe({ can_manage_news: d.user?.permissions?.can_manage_news })).catch(() => {});
```

显隐（约 94 行）：

```typescript
            {me?.can_manage_news && (
```

- [ ] **Step 3: `NewsFormPage.tsx`（约 63 行）**

```typescript
      .then((d: any) => setAllowed(!!d.user?.permissions?.can_manage_news))
```

- [ ] **Step 4: 构建**

```bash
cd frontend && npm run build
```
预期：EXIT 0（ts-loader 类型检查通过）。

- [ ] **Step 5: 提交**

```bash
cd /e/Backend && git add frontend/src/components/AppShell.tsx frontend/src/pages/NewsListPage.tsx frontend/src/pages/NewsFormPage.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): AppShell/News 改读 permissions.can_manage_news

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: 前端——Proposals（List + Detail）

**Files:**
- Modify: `frontend/src/pages/ProposalListPage.tsx`
- Modify: `frontend/src/pages/ProposalDetailPage.tsx`

- [ ] **Step 1: `ProposalListPage.tsx`——`isPresident` 全替换为 `canViewFeedback`**

接口（约 23 行）：

```typescript
  can_view_feedback?: boolean;
```

fetch（约 50 行）：

```typescript
      .then((d) => setUser({ id: d.user.id, username: d.user.username, can_view_feedback: d.user.permissions?.can_view_feedback }))
```

定义（约 54 行）：

```typescript
  const canViewFeedback = !!user?.can_view_feedback;
```

随后把文件中所有 `isPresident`（约 59、62、105、276、280 行）替换为 `canViewFeedback`。

- [ ] **Step 2: `ProposalDetailPage.tsx`——按能力拆分**

接口（约 23 行）改为：

```typescript
  can_approve_proposals?: boolean;
  can_change_proposals?: boolean;
  can_view_feedback?: boolean;
```

fetch（约 49 行）：

```typescript
    api.me().then((d) => setCurrentUser({
      id: d.user.id,
      can_approve_proposals: d.user.permissions?.can_approve_proposals,
      can_change_proposals: d.user.permissions?.can_change_proposals,
      can_view_feedback: d.user.permissions?.can_view_feedback,
    })).catch(() => {});
```

定义（约 79 行，替换 `const isPresident = ...`）：

```typescript
  const canApproveProposals = !!currentUser?.can_approve_proposals;
  const canChangeProposals = !!currentUser?.can_change_proposals;
  const canViewFeedback = !!currentUser?.can_view_feedback;
```

能力派生（约 222–226 行）：

```typescript
  const canApprove = canApproveProposals && p.status === "pending_approval";
  const canEdit = isActivity && p.status === "returned" && (isCreator || canChangeProposals);
  const canResubmit = isActivity && p.status === "returned" && (isCreator || canChangeProposals);
  const canManageAttachment = isActivity && (canChangeProposals || isCreator);
```

反馈详情（约 330 行）：

```typescript
                {!isActivity && p.contact && canViewFeedback && (
```

- [ ] **Step 3: 构建**

```bash
cd frontend && npm run build
```
预期：EXIT 0。

- [ ] **Step 4: 提交**

```bash
cd /e/Backend && git add frontend/src/pages/ProposalListPage.tsx frontend/src/pages/ProposalDetailPage.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): 申报列表/详情按 can_view_feedback / can_approve_proposals / can_change_proposals 驱动

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: 前端——TaskDetailPage

**Files:**
- Modify: `frontend/src/pages/TaskDetailPage.tsx`

- [ ] **Step 1: state（约 29 行）**

```typescript
  const [currentUser, setCurrentUser] = useState<{ id: number; can_manage_tasks?: boolean } | null>(null);
```

- [ ] **Step 2: fetch（约 35 行）**

```typescript
    api.me().then((d) => setCurrentUser({ id: d.user.id, can_manage_tasks: d.user.permissions?.can_manage_tasks })).catch(() => {});
```

- [ ] **Step 3: 定义 + 派生（约 213、216–218、345 行）**

```typescript
  const canManageTasks = !!currentUser?.can_manage_tasks;
```

```typescript
  const canComplete = task && task.status === "in_progress" && (!!isAssignee || canManageTasks);
  const canReviewCompletion = task && task.status === "reviewing" && (!!isCreator || canManageTasks);
  const canCancel = task && task.status !== "completed" && task.status !== "cancelled" && (!!isCreator || canManageTasks);
```

```typescript
        {(!!isCreator || canManageTasks) && pendingClaims.length > 0 && (
```

- [ ] **Step 4: 构建**

```bash
cd frontend && npm run build
```
预期：EXIT 0。

- [ ] **Step 5: 提交**

```bash
cd /e/Backend && git add frontend/src/pages/TaskDetailPage.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): 任务详情按 can_manage_tasks 驱动流转动作

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: 全量验证 + 收尾

**Files:** 仅验证，不改代码（必要时更新 memory）。

- [ ] **Step 1: 残留扫描**

```bash
cd /e/Backend && grep -rn "is_president\|is_info_group\|PRESIDENT_GROUP\|INFO_GROUP\b" --include="*.py" accounts news tasks proposals config
grep -rn "is_president\|is_info_group" --include="*.ts" --include="*.tsx" frontend/src
```
预期：无命中（`news/migrations/0002` 的 `INFO_GROUP_NAME` 不算）。

- [ ] **Step 2: 后端全量测试**

```bash
uv run python manage.py test
```
预期：全绿。

- [ ] **Step 3: 前端构建**

```bash
cd frontend && npm run build
```
预期：EXIT 0。

- [ ] **Step 4: 手动 smoke（Playwright 或浏览器）**

需后端 `uv run python manage.py runserver` + 前端 `npm run dev`（均已重启）。

1. 信息组用户登录 → `/news` 见「写新闻」、可进撰写页发布。
2. 普通用户 → 「写新闻」不显示；直接访问 `/news/new` 被挡（warning）。
3. 社长登录 → `/activity` 见反馈 tab、可审批申报、可改已打回申报/附件。
4. 普通用户 → 反馈 tab 不见、申报无审批按钮。
5. 社长 → `/tasks` 可流转任意任务（认领审批/验收/取消）。
6. 控制台 0 错误。

- [ ] **Step 5: 更新 memory `spa-backend-app-integration.md`**

在「role-gating pattern」段补记：角色→权限迁移已完成；鉴权用 `has_perm`，信息组/社长为默认组（`accounts/migrations/0004` 赋权）；`/auth/me/` 返回 `permissions.can_*` 能力字典（7 项）；news 写用 DRF `DjangoModelPermissionsOrAnonReadOnly`，tasks/proposals 保留自定义类（对象级/状态规则）但内核换 has_perm；通知路由 `_proposal_approvers()` 按权限查。

- [ ] **Step 6: 本地合 main（不推 origin）**

```bash
git checkout main && git merge roles-to-permissions --no-ff && git branch -d roles-to-permissions
```
（`--no-ff` 保留特性历史；确认后可。）

---

## 自检（写作后）

- **spec 覆盖**：权限集（Task 2）、默认组赋权（Task 3）、has_perm 执行（Task 4 keystone + Task 6/7）、news 内置类（Task 5）、API 能力字典（Task 8）、前端 6 处（Task 10–12）、清理与验证（Task 9/13）——全部覆盖；`can_change_proposals`（spec 第 7 能力）已在 Task 8/11 落地。
- **占位符**：无 TBD/TODO；每步含实码或确切命令与预期输出。
- **类型/命名一致**：能力键 `can_manage_news/can_manage_tasks/can_assign_task/can_manage_tags/can_approve_proposals/can_change_proposals/can_view_feedback` 在 `_capabilities`（Task 8）与前端（Task 10–12）逐字一致；权限代号 `tasks.manage_tasks/assign_task/manage_tags`、`proposals.approve_proposal/view_feedback/change_proposal`、`news.add_news` 在 Meta（Task 2）、赋权（Task 3）、执行（Task 4/6/7）一致。
- **删除顺序安全**：`is_president`/`is_info_group` 在所有导入方（accounts Task 8、proposals Task 7、tasks/views Task 6）更新后才于 Task 9 删除。
