# 个人中心重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把个人中心从一页表单重构为「Hero 卡片 + 侧栏/横向 tab + 内容区」，支持看别人主页（裁剪字段）、按身份显隐 tab、新增权限展示 tab，并让各处头像可点击跳转 `/u/<id>`。

**Architecture:** 统一路由 `/u/:id` + 服务端 `viewer` 标志驱动身份分支（自己 / 别人 / 管理员）。后端在 `accounts` 加 2 个端点（profile / content），可见性服务端强制；前端拆为 `UserProfile` 编排页 + 8 个 profile 子组件 + 专属 CSS。tab 状态走 `?tab=` 查询参数。

**Tech Stack:** Django 6.0（function views，`@login_required`）/ React 19 + TypeScript / cobalt 设计系统（`frontend/src/styles/*.css` 的 CSS 变量）/ React Router v6（`useSearchParams`）。前端无 JS 测试运行器——前端任务以 `npm run build` 通过 + 手动冒烟为准；后端走 Django `TestCase`（TDD）。

**Spec:** `docs/superpowers/specs/2026-07-21-profile-center-refactor-design.md`

**约定**
- 后端测试：`uv run python manage.py test accounts.<TestClass> -v 2`
- 前端构建（类型 + 打包）：`cd frontend && npm run build`
- 提交信息用中文，每次 task 末尾提交一次。

**⚠️ 前置处理（Task 1 之前必做）：** `accounts/views.py` 目前有 3 处**未提交的** `# type: ignore` 改动（第 74 / 115 / 268 行，给 `user.id` / `r.id` / `u.id` 静音类型检查）——这不在本特性范围内。因为 Task 1–3 都改这个文件，直接 `git add accounts/views.py` 会把它们一起带进本特性的提交。开工前先和用户确认怎么处理：**(a)** 先单独提一个 `chore: 给 .id 表达式补 type: ignore`（推荐，历史最干净）；**(b)** 暂时 `git stash`，特性做完再 pop；**(c)** 明确同意随本特性一起提交。确定后再开始 Task 1。

---

## Task 1: 后端 `_role_for` 主角色辅助函数（TDD）

**Files:**
- Modify: `accounts/views.py`（新增 `ROLE_PRIORITY` 常量与 `_role_for`）
- Test: `accounts/tests.py`（新增 `RoleForTest`）

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 末尾追加：

```python
class RoleForTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_president_wins_over_info(self):
        from django.contrib.auth.models import Group
        self.user.groups.add(Group.objects.get_or_create(name="社长")[0])
        self.user.groups.add(Group.objects.get_or_create(name="信息组")[0])
        from .views import _role_for
        self.assertEqual(_role_for(self.user), {"label": "社长", "variant": "president"})

    def test_info_group(self):
        from django.contrib.auth.models import Group
        self.user.groups.add(Group.objects.get_or_create(name="信息组")[0])
        from .views import _role_for
        self.assertEqual(_role_for(self.user), {"label": "信息组", "variant": "info"})

    def test_plain_member(self):
        from .views import _role_for
        self.assertEqual(_role_for(self.user), {"label": "成员", "variant": "member"})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python manage.py test accounts.RoleForTest -v 2`
Expected: FAIL（`ImportError: cannot import name '_role_for'`）

- [ ] **Step 3: 实现 `_role_for`**

在 `accounts/views.py` 的 `_capabilities` 函数**之后**插入：

```python
ROLE_PRIORITY = ["社长", "信息组"]  # 前者优先；都不在则归 "member"


def _role_for(user):
    """主角色 {label, variant}：社长 > 信息组 > 成员。variant 供前端配色。"""
    user_groups = set(user.groups.values_list("name", flat=True))
    for name in ROLE_PRIORITY:
        if name in user_groups:
            return {"label": name, "variant": "president" if name == "社长" else "info"}
    return {"label": "成员", "variant": "member"}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python manage.py test accounts.RoleForTest -v 2`
Expected: PASS（3 个）

- [ ] **Step 5: 提交**

```bash
git add accounts/views.py accounts/tests.py
git commit -m "feat(accounts): 新增 _role_for 主角色辅助（社长>信息组>成员）"
```

---

## Task 2: 后端 `GET /auth/users/<id>/profile/`（TDD）

**Files:**
- Modify: `accounts/views.py`（新增 `user_profile_view`）
- Modify: `accounts/urls.py`（新增 1 条 path）
- Test: `accounts/tests.py`（新增 `UserProfileViewTest`）

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 末尾追加：

```python
class UserProfileViewTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        self.viewed = User.objects.create_user(username="viewed", email="v@e.com", password="p")
        self.viewer = User.objects.create_user(username="viewer", password="p")
        self.admin = User.objects.create_user(username="admin", password="p")
        self.admin.groups.add(Group.objects.get_or_create(name="信息组")[0])

    def _login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_unauthenticated_redirects(self):
        self.assertEqual(Client().get(f"/auth/users/{self.viewed.id}/profile/").status_code, 302)

    def test_unknown_user_404(self):
        c = self._login(self.viewer)
        self.assertEqual(c.get("/auth/users/999999/profile/").status_code, 404)

    def test_public_viewer_does_not_see_private_fields(self):
        data = self._login(self.viewer).get(f"/auth/users/{self.viewed.id}/profile/").json()
        self.assertEqual(data["user"]["id"], self.viewed.id)
        self.assertEqual(data["user"]["username"], "viewed")
        self.assertIn("date_joined", data["user"])
        for k in ("avatar", "nickname", "bio"):
            self.assertIn(k, data["profile"])
        self.assertIn("role", data)
        self.assertEqual(data["viewer"], {"is_owner": False, "is_admin": False})
        self.assertNotIn("email", data["user"])
        self.assertNotIn("birthday", data["profile"])
        self.assertNotIn("gender", data["profile"])
        self.assertNotIn("permissions", data)
        self.assertNotIn("groups", data)

    def test_owner_sees_everything(self):
        data = self._login(self.viewed).get(f"/auth/users/{self.viewed.id}/profile/").json()
        self.assertTrue(data["viewer"]["is_owner"])
        self.assertEqual(data["user"]["email"], "v@e.com")
        self.assertIn("birthday", data["profile"])
        self.assertIn("gender", data["profile"])
        self.assertIn("permissions", data)
        self.assertIn("groups", data)

    def test_admin_sees_permissions_but_not_private_fields(self):
        data = self._login(self.admin).get(f"/auth/users/{self.viewed.id}/profile/").json()
        self.assertTrue(data["viewer"]["is_admin"])
        self.assertFalse(data["viewer"]["is_owner"])
        self.assertIn("permissions", data)
        self.assertIn("groups", data)
        self.assertNotIn("email", data["user"])
        self.assertNotIn("birthday", data["profile"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python manage.py test accounts.UserProfileViewTest -v 2`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 实现 view + URL**

在 `accounts/views.py`，`profile_view` 附近新增（注意顶部已 import `User`、`Profile`、`JsonResponse`、`require_GET`、`login_required`）：

```python
@require_GET
@login_required
def user_profile_view(request, id):
    """查看任意用户的主页资料（按请求者身份裁剪字段）。"""
    viewed = User.objects.filter(pk=id, is_active=True).first()
    if viewed is None:
        return JsonResponse({"error": "用户不存在"}, status=404)

    profile = _get_or_create_profile(viewed)
    is_owner = request.user.id == viewed.id
    is_admin = request.user.is_superuser or request.user.groups.filter(name="信息组").exists()

    data = {
        "user": {
            "id": viewed.id,
            "username": viewed.username,
            "date_joined": viewed.date_joined.isoformat(),
        },
        "profile": {
            "avatar": profile.avatar.url if profile.avatar else None,
            "nickname": profile.nickname,
            "bio": profile.bio,
        },
        "role": _role_for(viewed),
        "viewer": {"is_owner": is_owner, "is_admin": is_admin},
    }

    if is_owner:
        data["user"]["email"] = viewed.email
        data["profile"]["birthday"] = profile.birthday.isoformat() if profile.birthday else None
        data["profile"]["gender"] = profile.gender

    if is_owner or is_admin:
        data["permissions"] = _capabilities(viewed)
        data["groups"] = list(viewed.groups.values_list("name", flat=True))

    return JsonResponse(data)
```

在 `accounts/urls.py` 的 `urlpatterns` 里，`path("users/", ...)` **之后**加：

```python
    path("users/<int:id>/profile/", views.user_profile_view, name="user_profile"),
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python manage.py test accounts.UserProfileViewTest -v 2`
Expected: PASS（5 个）

- [ ] **Step 5: 提交**

```bash
git add accounts/views.py accounts/urls.py accounts/tests.py
git commit -m "feat(accounts): GET /auth/users/<id>/profile/ 按身份裁剪字段"
```

---

## Task 3: 后端 `GET /auth/users/<id>/content/?type=`（TDD）

**Files:**
- Modify: `accounts/views.py`（新增 `CONTENT_LIMIT` 与 `user_content_view`）
- Modify: `accounts/urls.py`（新增 1 条 path）
- Test: `accounts/tests.py`（新增 `UserContentViewTest`）

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 末尾追加：

```python
class UserContentViewTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="p")
        self.other = User.objects.create_user(username="other", password="p")

    def _login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def _get(self, client, type_):
        return client.get(f"/auth/users/{self.owner.id}/content/?type={type_}")

    def test_unauthenticated_redirects(self):
        self.assertEqual(Client().get(f"/auth/users/{self.owner.id}/content/?type=news").status_code, 302)

    def test_unknown_user_404(self):
        c = self._login(self.other)
        self.assertEqual(c.get("/auth/users/999999/content/?type=news").status_code, 404)

    def test_invalid_type_400(self):
        c = self._login(self.other)
        self.assertEqual(self._get(c, "bogus").status_code, 400)

    def test_news_owner_sees_drafts_public_does_not(self):
        from news.models import News
        News.objects.create(title="published", author=self.owner, is_published=True)
        News.objects.create(title="draft", author=self.owner, is_published=False)
        owner = {r["title"] for r in self._get(self._login(self.owner), "news").json()["results"]}
        self.assertEqual(owner, {"published", "draft"})
        other = {r["title"] for r in self._get(self._login(self.other), "news").json()["results"]}
        self.assertEqual(other, {"published"})

    def test_proposals_public_sees_only_approved(self):
        from proposals.models import Proposal
        Proposal.objects.create(title="approved", proposal_type="activity", status="approved", creator=self.owner)
        Proposal.objects.create(title="pending", proposal_type="activity", status="pending_approval", creator=self.owner)
        other = {r["title"] for r in self._get(self._login(self.other), "proposals").json()["results"]}
        self.assertEqual(other, {"approved"})
        owner = {r["title"] for r in self._get(self._login(self.owner), "proposals").json()["results"]}
        self.assertEqual(owner, {"approved", "pending"})

    def test_tasks_owner_ok_other_403(self):
        from tasks.models import Task
        Task.objects.create(title="t", creator=self.owner, assignee=self.owner)
        owner_resp = self._get(self._login(self.owner), "tasks")
        self.assertEqual(owner_resp.status_code, 200)
        self.assertEqual(len(owner_resp.json()["results"]), 1)
        self.assertEqual(self._get(self._login(self.other), "tasks").status_code, 403)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python manage.py test accounts.UserContentViewTest -v 2`
Expected: FAIL（路由不存在）

- [ ] **Step 3: 实现 view + URL**

在 `accounts/views.py` 顶部常量区（`LOGIN_PROTECTION_SECONDS` 附近）加：

```python
CONTENT_LIMIT = 15  # 个人中心每个内容 tab 返回的最近条数
```

在 `user_profile_view` 之后新增：

```python
@require_GET
@login_required
def user_content_view(request, id):
    """某用户的 tab 内容（按身份裁剪可见性）。"""
    viewed = User.objects.filter(pk=id, is_active=True).first()
    if viewed is None:
        return JsonResponse({"error": "用户不存在"}, status=404)

    is_owner = request.user.id == viewed.id
    type_ = request.GET.get("type")
    if type_ not in ("news", "proposals", "tasks"):
        return JsonResponse({"error": "无效的 type"}, status=400)

    if type_ == "news":
        from news.models import News
        qs = News.objects.filter(author=viewed)
        if not is_owner:
            qs = qs.filter(is_published=True)
        results = [{
            "id": n.id,
            "title": n.title,
            "category": n.category,
            "cover_image": n.cover_image.url if n.cover_image else None,
            "is_published": n.is_published,
            "published_at": (n.published_at or n.created_at).isoformat(),
        } for n in qs[:CONTENT_LIMIT]]

    elif type_ == "proposals":
        from proposals.models import Proposal
        qs = Proposal.objects.filter(creator=viewed)
        if not is_owner:
            qs = qs.filter(status="approved")
        results = [{
            "id": p.id,
            "title": p.title,
            "proposal_type": p.proposal_type,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
        } for p in qs[:CONTENT_LIMIT]]

    else:  # tasks
        if not is_owner:
            return JsonResponse({"error": "无权查看他人任务"}, status=403)
        from tasks.models import Task
        qs = Task.objects.filter(assignee=viewed)
        results = [{
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at.isoformat(),
        } for t in qs[:CONTENT_LIMIT]]

    return JsonResponse({"results": results})
```

在 `accounts/urls.py`，Task 2 加的那条之后再加：

```python
    path("users/<int:id>/content/", views.user_content_view, name="user_content"),
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python manage.py test accounts.UserContentViewTest -v 2`
Expected: PASS（6 个）

- [ ] **Step 5: 跑全部 accounts 测试确认无回归**

Run: `uv run python manage.py test accounts -v 1`
Expected: 全 PASS

- [ ] **Step 6: 提交**

```bash
git add accounts/views.py accounts/urls.py accounts/tests.py
git commit -m "feat(accounts): GET /auth/users/<id>/content/ 按身份裁剪内容可见性"
```

---

## Task 4: 前端 API 方法 + 类型 + 角色徽章映射

**Files:**
- Modify: `frontend/src/api/client.ts`（增 2 方法）
- Create: `frontend/src/types/profile.ts`

- [ ] **Step 1: 新建类型文件**

创建 `frontend/src/types/profile.ts`：

```ts
export type RoleVariant = "president" | "info" | "member";

export interface UserProfileData {
  user: { id: number; username: string; date_joined: string; email?: string };
  profile: {
    avatar: string | null;
    nickname: string;
    bio: string;
    birthday?: string | null;
    gender?: string;
  };
  role: { label: string; variant: RoleVariant };
  viewer: { is_owner: boolean; is_admin: boolean };
  permissions?: Record<string, boolean>;
  groups?: string[];
}

export type ContentType = "news" | "proposals" | "tasks";

export interface ContentItem {
  id: number;
  title: string;
  created_at?: string;
  published_at?: string;
  category?: string;
  cover_image?: string | null;
  is_published?: boolean;
  proposal_type?: string;
  status?: string;
  priority?: string;
}

/** 角色 variant → 徽章 CSS 类（配色在 styles/profile.css） */
export const ROLE_BADGE: Record<RoleVariant, string> = {
  president: "badge-role-president",
  info: "badge-role-info",
  member: "badge-role-member",
};
```

- [ ] **Step 2: 给 api/client.ts 加 2 个方法**

在 `frontend/src/api/client.ts` 的 `listUsers` 之后、`};` 之前加：

```ts
  getUserProfile: (id: number) =>
    request(`/users/${id}/profile/`),

  getUserContent: (id: number, type: "news" | "proposals" | "tasks") =>
    request(`/users/${id}/content/?type=${type}`),
```

- [ ] **Step 3: 构建确认类型无误**

Run: `cd frontend && npm run build`
Expected: 构建成功（无 TS 报错）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/profile.ts frontend/src/api/client.ts
git commit -m "feat(frontend): 个人中心 API 方法 + 类型 + 角色徽章映射"
```

---

## Task 5: 前端 profile 样式 + ProfileHero

**Files:**
- Create: `frontend/src/styles/profile.css`
- Create: `frontend/src/components/profile/ProfileHero.tsx`

- [ ] **Step 1: 新建样式文件**

创建 `frontend/src/styles/profile.css`：

```css
/* 个人中心：Hero 卡片 + 侧栏/横向 tab + 面板。cobalt 令牌取自 styles/cobalt.css */

/* ── Hero ── */
.profile-hero { position: relative; border-bottom: 1px solid var(--line); }
.profile-hero-cover { height: 120px; background: linear-gradient(135deg, var(--brand-700), var(--brand-400)); }
.profile-hero-body { display: flex; align-items: flex-end; gap: var(--s-5); padding-bottom: var(--s-6); flex-wrap: wrap; }
.profile-hero-avatar {
  width: 96px; height: 96px; border-radius: var(--r-pill);
  background: var(--brand-100); color: var(--brand-700);
  display: grid; place-items: center; font-size: 36px; font-weight: 700;
  margin-top: -48px; border: 4px solid var(--bg); overflow: hidden; box-shadow: var(--sh-1);
}
.profile-hero-avatar img { width: 100%; height: 100%; object-fit: cover; }
.profile-hero-meta { flex: 1; min-width: 220px; }
.profile-hero-name { display: flex; align-items: center; gap: var(--s-3); font-size: 24px; }
.profile-role-badge { font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: var(--r-pill); color: #fff; }
.badge-role-president { background: var(--warning); }
.badge-role-info { background: var(--brand-600); }
.badge-role-member { background: var(--ink-400); }
.profile-hero-sub { color: var(--muted); font-size: 13px; margin-top: 2px; }
.profile-hero-bio { margin-top: var(--s-2); max-width: 60ch; }
.profile-hero-edit { align-self: flex-end; }

/* ── 布局 ── */
.profile-body { padding-top: var(--s-6); padding-bottom: var(--s-16); }
.profile-layout { display: grid; grid-template-columns: var(--rail-w) 1fr; gap: var(--s-6); align-items: start; }

/* 自己：左侧垂直 nav */
.profile-sidenav { position: sticky; top: calc(var(--nav-h) + var(--s-4)); display: flex; flex-direction: column; gap: 2px; }
.profile-nav-item { text-align: left; padding: var(--s-2) var(--s-4); border-radius: var(--r-md); color: var(--ink-700); font-weight: 500; }
.profile-nav-item:hover { background: var(--surface-2); }
.profile-nav-item.active { background: var(--brand-50); color: var(--brand-700); }

/* 别人：横向 tab 条 */
.profile-other { display: flex; flex-direction: column; gap: var(--s-4); }
.profile-tabs { display: flex; gap: var(--s-2); border-bottom: 1px solid var(--line); }
.profile-tab { padding: var(--s-2) var(--s-4); color: var(--ink-700); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.profile-tab.active { color: var(--brand-700); border-bottom-color: var(--brand-700); font-weight: 600; }

/* ── 面板 ── */
.profile-panel { min-height: 200px; }
.profile-panel-title { font-size: 18px; margin-bottom: var(--s-4); }

.profile-content-list { display: flex; flex-direction: column; }
.profile-content-item {
  padding: var(--s-3) var(--s-4); border: 1px solid var(--line); border-radius: var(--r-md);
  margin-bottom: var(--s-2); cursor: pointer; transition: border-color var(--dur-1) var(--ease);
}
.profile-content-item:hover { border-color: var(--brand-400); }
.pci-title { font-weight: 600; }
.pci-meta { color: var(--muted); font-size: 13px; margin-top: 2px; }

.profile-sessions { display: flex; flex-direction: column; }
.profile-session { display: flex; align-items: center; justify-content: space-between; gap: var(--s-3); padding: var(--s-3) 0; border-bottom: 1px solid var(--line); }
.profile-session:last-child { border-bottom: none; }
.ps-name { font-weight: 600; }
.ps-sub { font-size: 13px; }

.profile-perms { display: flex; flex-direction: column; gap: var(--s-2); }
.profile-perm { display: flex; align-items: center; justify-content: space-between; padding: var(--s-2) var(--s-3); border-radius: var(--r-md); background: var(--bg-soft); }
.badge-ghost { background: var(--surface-2); color: var(--muted); }

@media (max-width: 820px) {
  .profile-layout { grid-template-columns: 1fr; }
  .profile-sidenav { position: static; flex-direction: row; overflow-x: auto; }
  .profile-nav-item { white-space: nowrap; }
}
```

- [ ] **Step 2: 新建 ProfileHero 组件**

创建 `frontend/src/components/profile/ProfileHero.tsx`：

```tsx
import type { UserProfileData } from "../../types/profile";
import { ROLE_BADGE } from "../../types/profile";

interface Props {
  profile: UserProfileData;
  /** 自己看自己时传入（跳到资料编辑 tab）；别人看时为 undefined */
  onEdit?: () => void;
}

export default function ProfileHero({ profile, onEdit }: Props) {
  const { user, profile: p, role } = profile;
  const name = p.nickname || user.username;
  const initial = name.charAt(0).toUpperCase();
  const d = new Date(user.date_joined);
  const joined = isNaN(d.getTime())
    ? ""
    : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

  return (
    <section className="profile-hero">
      <div className="profile-hero-cover" />
      <div className="profile-hero-body container">
        <div className="profile-hero-avatar">
          {p.avatar ? <img src={p.avatar} alt="" /> : <span>{initial}</span>}
        </div>
        <div className="profile-hero-meta">
          <h1 className="profile-hero-name">
            {name}
            <span className={`profile-role-badge ${ROLE_BADGE[role.variant]}`}>{role.label}</span>
          </h1>
          {joined && <p className="profile-hero-sub">注册于 {joined}</p>}
          <p className={"profile-hero-bio" + (p.bio ? "" : " muted")}>{p.bio || "这个人很懒，什么都没有写……"}</p>
        </div>
        {onEdit && <button className="btn btn-primary btn-sm profile-hero-edit" onClick={onEdit}>编辑资料</button>}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: 构建确认**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add frontend/src/styles/profile.css frontend/src/components/profile/ProfileHero.tsx
git commit -m "feat(frontend): profile 样式 + ProfileHero 卡片"
```

---

## Task 6: 前端 导航组件（侧栏 + 横向 tab）

**Files:**
- Create: `frontend/src/components/profile/ProfileSideNav.tsx`
- Create: `frontend/src/components/profile/ProfileTabs.tsx`

- [ ] **Step 1: 新建两个导航组件**

创建 `frontend/src/components/profile/ProfileSideNav.tsx`：

```tsx
interface TabDef { key: string; label: string; }
interface Props { tabs: TabDef[]; active: string; onPick: (key: string) => void; }

export default function ProfileSideNav({ tabs, active, onPick }: Props) {
  return (
    <nav className="profile-sidenav" aria-label="个人中心导航">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          className={"profile-nav-item" + (t.key === active ? " active" : "")}
          aria-current={t.key === active ? "true" : undefined}
          onClick={() => onPick(t.key)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
```

创建 `frontend/src/components/profile/ProfileTabs.tsx`：

```tsx
interface TabDef { key: string; label: string; }
interface Props { tabs: TabDef[]; active: string; onPick: (key: string) => void; }

export default function ProfileTabs({ tabs, active, onPick }: Props) {
  return (
    <nav className="profile-tabs" aria-label="个人中心导航">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          className={"profile-tab" + (t.key === active ? " active" : "")}
          aria-current={t.key === active ? "true" : undefined}
          onClick={() => onPick(t.key)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: 构建确认**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/profile/ProfileSideNav.tsx frontend/src/components/profile/ProfileTabs.tsx
git commit -m "feat(frontend): profile 侧栏 nav + 横向 tab 组件"
```

---

## Task 7: 前端 资料/密码/会话 三个面板（从旧 ProfilePage 搬运）

**Files:**
- Create: `frontend/src/components/profile/ProfileEditPanel.tsx`
- Create: `frontend/src/components/profile/PasswordPanel.tsx`
- Create: `frontend/src/components/profile/SessionsPanel.tsx`

> 这三个面板的逻辑与旧 `pages/ProfilePage.tsx` 完全一致，只是拆成独立组件、各自挂在 tab 下面。表单样式复用现成的 `styles/form.css` 类（`card / card-pad / form-stack / field / label / input / select / textarea / form-grid / form-actions / avatar-upload / avatar / au-meta / au-hint / alert` 等）。

- [ ] **Step 1: ProfileEditPanel**

创建 `frontend/src/components/profile/ProfileEditPanel.tsx`：

```tsx
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../../api/client";
import "../../styles/form.css";

const GENDER_OPTIONS = [
  { value: "", label: "未设置" },
  { value: "M", label: "男" },
  { value: "F", label: "女" },
  { value: "O", label: "其他" },
];

/** 资料编辑面板（仅自己可用）。保存成功后调 onSaved，由父组件刷新 Hero + 顶栏。 */
export default function ProfileEditPanel({ onSaved }: { onSaved: () => void }) {
  const [nickname, setNickname] = useState("");
  const [birthday, setBirthday] = useState("");
  const [gender, setGender] = useState("");
  const [bio, setBio] = useState("");
  const [avatar, setAvatar] = useState<string | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getProfile()
      .then((d: any) => {
        setNickname(d.profile.nickname);
        setBirthday(d.profile.birthday || "");
        setGender(d.profile.gender);
        setBio(d.profile.bio);
        setAvatar(d.profile.avatar);
      })
      .finally(() => setLoading(false));
  }, []);

  const onAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 2 * 1024 * 1024) { setError("头像文件不能超过 2MB"); return; }
    const reader = new FileReader();
    reader.onload = (ev) => setAvatarPreview(ev.target?.result as string);
    reader.readAsDataURL(f);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(""); setSaving(true);
    try {
      const fd = new FormData();
      if (avatarPreview) {
        const f = fileRef.current?.files?.[0];
        if (f) fd.append("avatar", f);
      }
      fd.append("nickname", nickname);
      fd.append("birthday", birthday);
      fd.append("gender", gender);
      fd.append("bio", bio);
      await api.updateProfile(fd);
      setAvatarPreview(null);
      setSuccess("资料已更新");
      setTimeout(() => setSuccess(""), 3000);
      onSaved();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="muted">加载中…</p>;

  const avatarSrc = avatarPreview || avatar;
  const initial = (nickname || "?").charAt(0).toUpperCase();

  return (
    <form className="card card-pad form-stack" onSubmit={submit}>
      {success && <div className="alert alert-success"><span>{success}</span></div>}
      {error && <div className="alert alert-danger"><span>{error}</span></div>}

      <div className="avatar-upload">
        <div className="avatar editable" onClick={() => fileRef.current?.click()} role="button">
          {avatarSrc ? <img src={avatarSrc} alt="头像" /> : <span>{initial}</span>}
          <span className="cam">✎</span>
        </div>
        <div className="au-meta">
          <span className="au-hint">点击头像更换 · 不超过 2MB</span>
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => fileRef.current?.click()}>更换头像</button>
        </div>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={onAvatarChange} style={{ display: "none" }} />
      </div>

      <div className="field">
        <label className="label">昵称</label>
        <input className="input" type="text" value={nickname} onChange={(e) => setNickname(e.target.value)} maxLength={50} placeholder="设置昵称" />
      </div>
      <div className="form-grid">
        <div className="field">
          <label className="label">生日</label>
          <input className="input" type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)} />
        </div>
        <div className="field">
          <label className="label">性别</label>
          <select className="select" value={gender} onChange={(e) => setGender(e.target.value)}>
            {GENDER_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label className="label">个人简介</label>
        <textarea className="textarea" value={bio} onChange={(e) => setBio(e.target.value)} maxLength={500} rows={3} placeholder="介绍一下自己吧" />
      </div>

      <div className="form-actions">
        <button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "保存中…" : "保存"}</button>
      </div>
    </form>
  );
}
```

- [ ] **Step 2: PasswordPanel**

创建 `frontend/src/components/profile/PasswordPanel.tsx`：

```tsx
import { useState, type FormEvent } from "react";
import { api } from "../../api/client";
import "../../styles/form.css";

export default function PasswordPanel() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (newPassword !== confirm) { setError("两次输入的密码不一致"); return; }
    if (newPassword.length < 8) { setError("新密码至少 8 个字符"); return; }
    setSaving(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      setOldPassword(""); setNewPassword(""); setConfirm("");
      setSuccess("密码已修改");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card card-pad form-stack" onSubmit={submit}>
      {success && <div className="alert alert-success"><span>{success}</span></div>}
      {error && <div className="alert alert-danger"><span>{error}</span></div>}
      <div className="field">
        <label className="label">原密码</label>
        <input className="input" type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} required />
      </div>
      <div className="form-grid">
        <div className="field">
          <label className="label">新密码</label>
          <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
        </div>
        <div className="field">
          <label className="label">确认新密码</label>
          <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        </div>
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "修改中…" : "确认修改"}</button>
      </div>
    </form>
  );
}
```

- [ ] **Step 3: SessionsPanel**

创建 `frontend/src/components/profile/SessionsPanel.tsx`：

```tsx
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import "../../styles/form.css";

interface SessionRow {
  id: number;
  device_name: string;
  device_type: string;
  ip_address: string | null;
  created_at: string;
  is_current: boolean;
}

const DEVICE_TYPE_LABEL: Record<string, string> = {
  Desktop: "桌面端", Mobile: "手机", Tablet: "平板", Bot: "爬虫", Unknown: "未知",
};

const fmt = (iso: string): string => {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

export default function SessionsPanel() {
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);

  useEffect(() => {
    api.listSessions()
      .then((d: any) => setSessions(d.results))
      .catch(() => setSessions([]));
  }, []);

  return (
    <div className="card card-pad">
      <h2 className="profile-panel-title">登录记录</h2>
      {sessions === null ? (
        <p className="muted">加载中…</p>
      ) : sessions.length === 0 ? (
        <p className="muted">暂无登录记录</p>
      ) : (
        <ul className="profile-sessions">
          {sessions.map((s) => (
            <li key={s.id} className="profile-session">
              <div>
                <div className="ps-name">{s.device_name || "未知设备"}</div>
                <div className="muted ps-sub">
                  {DEVICE_TYPE_LABEL[s.device_type] ?? s.device_type}
                  {s.ip_address ? ` · ${s.ip_address}` : ""}
                  {" · " + fmt(s.created_at)}
                </div>
              </div>
              {s.is_current && <span className="badge badge-success">当前本机</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 构建确认**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/profile/ProfileEditPanel.tsx frontend/src/components/profile/PasswordPanel.tsx frontend/src/components/profile/SessionsPanel.tsx
git commit -m "feat(frontend): 资料/密码/会话 三个 profile 面板（搬运自旧 ProfilePage）"
```

---

## Task 8: 前端 内容列表面板 + 权限面板

**Files:**
- Create: `frontend/src/components/profile/ContentListPanel.tsx`
- Create: `frontend/src/components/profile/PermissionsPanel.tsx`

- [ ] **Step 1: ContentListPanel（新闻/申报/任务通用）**

创建 `frontend/src/components/profile/ContentListPanel.tsx`：

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { ContentType, ContentItem } from "../../types/profile";
import "../../styles/form.css";

const DETAIL_PATH: Record<ContentType, string> = {
  news: "/news",
  proposals: "/activity",
  tasks: "/tasks",
};

const NEWS_CATEGORY: Record<string, string> = {
  notice: "社团公告", recap: "活动回顾", work: "作品展示", inform: "通知",
};
const PROPOSAL_TYPE: Record<string, string> = {
  activity: "活动申报", feedback: "意见反馈",
};
const TASK_STATUS: Record<string, string> = {
  pending: "待处理", in_progress: "进行中", reviewing: "待验收", review: "审核中", completed: "已完成", cancelled: "已取消",
};
const TASK_PRIORITY: Record<string, string> = {
  low: "低", medium: "中", high: "高", urgent: "紧急",
};

function metaFor(type: ContentType, it: ContentItem): string {
  if (type === "news") {
    const cat = it.category ? NEWS_CATEGORY[it.category] ?? it.category : "";
    const draft = it.is_published === false ? " · 草稿" : "";
    return [cat, it.published_at?.slice(0, 10)].filter(Boolean).join(" · ") + draft;
  }
  if (type === "proposals") {
    return [it.proposal_type ? PROPOSAL_TYPE[it.proposal_type] ?? it.proposal_type : "", it.created_at?.slice(0, 10)]
      .filter(Boolean).join(" · ");
  }
  // tasks
  const st = it.status ? TASK_STATUS[it.status] ?? it.status : "";
  const pr = it.priority ? TASK_PRIORITY[it.priority] ?? it.priority : "";
  return [st, pr, it.created_at?.slice(0, 10)].filter(Boolean).join(" · ");
}

interface Props {
  userId: number;
  type: ContentType;
  selfView: boolean;
}

export default function ContentListPanel({ userId, type }: Props) {
  const [items, setItems] = useState<ContentItem[] | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    setItems(null);
    setError("");
    api.getUserContent(userId, type)
      .then((d: any) => setItems(d.results as ContentItem[]))
      .catch((e: any) => setError(e.status === 403 ? "无权查看" : "加载失败"));
  }, [userId, type]);

  if (error) return <p className="muted">{error}</p>;
  if (items === null) return <p className="muted">加载中…</p>;
  if (items.length === 0) return <p className="muted">暂无内容</p>;

  const go = (id: number) => navigate(`${DETAIL_PATH[type]}/${id}`);

  return (
    <ul className="profile-content-list">
      {items.map((it) => (
        <li
          key={it.id}
          className="profile-content-item"
          role="button"
          tabIndex={0}
          onClick={() => go(it.id)}
          onKeyDown={(e) => { if (e.key === "Enter") go(it.id); }}
        >
          <div className="pci-title">{it.title}</div>
          <div className="pci-meta">{metaFor(type, it)}</div>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 2: PermissionsPanel**

创建 `frontend/src/components/profile/PermissionsPanel.tsx`：

```tsx
import type { UserProfileData } from "../../types/profile";
import "../../styles/form.css";

const CAP_LABELS: Record<string, string> = {
  can_manage_news: "管理新闻",
  can_manage_tasks: "管理任务",
  can_assign_task: "指派任务",
  can_manage_tags: "管理标签",
  can_approve_proposals: "审批申报",
  can_change_proposals: "修改申报",
  can_view_feedback: "查看反馈",
};

export default function PermissionsPanel({ profile }: { profile: UserProfileData }) {
  const perms = profile.permissions ?? {};
  const groups = profile.groups ?? [];
  return (
    <div className="card card-pad">
      <h2 className="profile-panel-title">权限与角色</h2>
      <p className="muted" style={{ marginBottom: "var(--s-4)" }}>
        所属组：{groups.length ? groups.join("、") : "（无）"}
      </p>
      <ul className="profile-perms">
        {Object.entries(CAP_LABELS).map(([key, label]) => (
          <li key={key} className="profile-perm">
            <span>{label}</span>
            <span className={"badge " + (perms[key] ? "badge-success" : "badge-ghost")}>
              {perms[key] ? "有" : "无"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: 构建确认**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/profile/ContentListPanel.tsx frontend/src/components/profile/PermissionsPanel.tsx
git commit -m "feat(frontend): 内容列表面板 + 权限面板"
```

---

## Task 9: 前端 编排页 + 重定向 + 路由接线（删旧 ProfilePage）

**Files:**
- Create: `frontend/src/pages/UserProfile.tsx`
- Create: `frontend/src/pages/ProfileRedirect.tsx`
- Modify: `frontend/src/App.tsx`（路由）
- Delete: `frontend/src/pages/ProfilePage.tsx`

- [ ] **Step 1: 新建 UserProfile 编排页**

创建 `frontend/src/pages/UserProfile.tsx`：

```tsx
import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import { api } from "../api/client";
import { useLoginModal } from "../components/LoginModalProvider";
import ProfileHero from "../components/profile/ProfileHero";
import ProfileSideNav from "../components/profile/ProfileSideNav";
import ProfileTabs from "../components/profile/ProfileTabs";
import ProfileEditPanel from "../components/profile/ProfileEditPanel";
import PasswordPanel from "../components/profile/PasswordPanel";
import SessionsPanel from "../components/profile/SessionsPanel";
import ContentListPanel from "../components/profile/ContentListPanel";
import PermissionsPanel from "../components/profile/PermissionsPanel";
import type { UserProfileData } from "../types/profile";
import "../styles/profile.css";

const SELF_TABS = [
  { key: "profile", label: "资料编辑" },
  { key: "password", label: "改密码" },
  { key: "sessions", label: "登录记录" },
  { key: "news", label: "我的新闻" },
  { key: "proposals", label: "我的申报" },
  { key: "tasks", label: "我的任务" },
  { key: "permissions", label: "我的权限" },
];

export default function UserProfile() {
  const { id } = useParams<{ id: string }>();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const { openLogin, notifyAuthChange } = useLoginModal();
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadErr, setLoadErr] = useState("");

  const uid = Number(id);

  useEffect(() => {
    setProfile(null);
    setNotFound(false);
    setLoadErr("");
    api.getUserProfile(uid)
      .then((d: any) => setProfile(d))
      .catch((e: any) => {
        if (e.status === 401) openLogin();
        else if (e.status === 404) setNotFound(true);
        else setLoadErr(e.message || "加载失败");
      });
  }, [uid, openLogin]);

  if (notFound || loadErr) {
    return (
      <AppShell>
        <div className="container" style={{ paddingTop: "var(--s-12)" }}>
          <p className="muted">{notFound ? "用户不存在。" : loadErr}</p>
        </div>
      </AppShell>
    );
  }
  if (!profile) {
    return (
      <AppShell>
        <div className="container" style={{ paddingTop: "var(--s-12)" }}>
          <p className="muted">加载中…</p>
        </div>
      </AppShell>
    );
  }

  const isOwner = profile.viewer.is_owner;
  const isAdmin = profile.viewer.is_admin;

  const tabs = isOwner
    ? SELF_TABS
    : [
        { key: "news", label: "ta 的新闻" },
        { key: "proposals", label: "ta 的申报" },
        ...(isAdmin ? [{ key: "permissions", label: "权限" }] : []),
      ];

  const defaultTab = isOwner ? "profile" : "news";
  const tabKeys = tabs.map((t) => t.key);
  const active = tabKeys.includes(search.get("tab") || defaultTab) ? search.get("tab")! : defaultTab;

  const setTab = (k: string) => {
    const next = new URLSearchParams(search);
    next.set("tab", k);
    setSearch(next, { replace: true });
  };

  const onProfileSaved = () => {
    api.getUserProfile(uid).then((d: any) => setProfile(d)).catch(() => {});
    notifyAuthChange();
  };

  return (
    <AppShell>
      <ProfileHero profile={profile} onEdit={isOwner ? () => setTab("profile") : undefined} />

      <div className="container profile-body">
        {isOwner ? (
          <div className="profile-layout">
            <ProfileSideNav tabs={tabs} active={active} onPick={setTab} />
            <div className="profile-panel">
              {active === "profile" && <ProfileEditPanel onSaved={onProfileSaved} />}
              {active === "password" && <PasswordPanel />}
              {active === "sessions" && <SessionsPanel />}
              {active === "news" && <ContentListPanel userId={uid} type="news" selfView />}
              {active === "proposals" && <ContentListPanel userId={uid} type="proposals" selfView />}
              {active === "tasks" && <ContentListPanel userId={uid} type="tasks" selfView />}
              {active === "permissions" && <PermissionsPanel profile={profile} />}
            </div>
          </div>
        ) : (
          <div className="profile-other">
            <ProfileTabs tabs={tabs} active={active} onPick={setTab} />
            <div className="profile-panel">
              {active === "news" && <ContentListPanel userId={uid} type="news" selfView={false} />}
              {active === "proposals" && <ContentListPanel userId={uid} type="proposals" selfView={false} />}
              {active === "permissions" && <PermissionsPanel profile={profile} />}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 2: 新建 ProfileRedirect**

创建 `frontend/src/pages/ProfileRedirect.tsx`：

```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useLoginModal } from "../components/LoginModalProvider";

/** /profile → /u/<我的id>。需先取 me.id，所以是一个独立组件而不是静态 redirect。 */
export default function ProfileRedirect() {
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();
  useEffect(() => {
    api.me()
      .then((d: any) => navigate(`/u/${d.user.id}`, { replace: true }))
      .catch(() => openLogin());
  }, [navigate, openLogin]);
  return null;
}
```

- [ ] **Step 3: 改 App.tsx 路由**

在 `frontend/src/App.tsx`：

把第 11 行的 `const ProfilePage = lazy(() => import("./pages/ProfilePage"));` 替换为：

```tsx
const UserProfile = lazy(() => import("./pages/UserProfile"));
const ProfileRedirect = lazy(() => import("./pages/ProfileRedirect"));
```

把第 42 行的 `<Route path="/profile" element={<ProfilePage />} />` 替换为：

```tsx
      <Route path="/profile" element={<ProfileRedirect />} />
      <Route path="/u/:id" element={<UserProfile />} />
```

- [ ] **Step 4: 删除旧 ProfilePage**

```bash
git rm frontend/src/pages/ProfilePage.tsx
```

- [ ] **Step 5: 构建确认**

Run: `cd frontend && npm run build`
Expected: 构建成功（无 TS 报错、无未解析导入）

- [ ] **Step 6: 手动冒烟**

启动后端 `uv run python manage.py runserver` 与前端 `cd frontend && npm run dev`，登录后：

1. 顶栏「个人中心」→ 应跳 `/u/<你的id>`，默认停在「资料编辑」tab，左侧 7 项 nav，Hero 显示你的头像/昵称/角色徽章/简介。
2. 切到「我的新闻 / 我的申报 / 我的任务 / 登录记录 / 我的权限」逐一确认有内容/空态正常。
3. 改昵称保存 → Hero 与顶栏昵称同步刷新。
4. 手动访问 `/#/u/<别人id>` → Hero 只读、横向 2 个 tab（ta 的新闻 / ta 的申报），无编辑/改密/会话/任务/权限。
5. 用一个信息组账号访问 `/#/u/<别人id>` → 多出「权限」tab。
6. 访问 `/#/u/999999` → 显示「用户不存在。」
7. 把 URL 改成 `?tab=password` 访问别人 → 应回退到「ta 的新闻」。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/pages/UserProfile.tsx frontend/src/pages/ProfileRedirect.tsx frontend/src/App.tsx
git commit -m "feat(frontend): UserProfile 编排页 + /profile 重定向 + 路由接线，移除旧 ProfilePage"
```

> 注意：`git rm` 已暂存删除；若 `git status` 显示 ProfilePage.tsx 为待提交删除，确认它进入了本次提交（`git add` 步骤只加了新增/修改文件，删除需单独 `git rm`，已在 Step 4 完成）。

---

## Task 10: 前端 各处头像可点击跳转 `/u/<id>`

**Files:**
- Modify: `frontend/src/pages/NewsDetailPage.tsx`（作者头像）
- Modify: `frontend/src/pages/ProposalListPage.tsx`（创建人头像）
- Modify: `frontend/src/pages/TaskListPage.tsx`（负责人头像）
- Modify（同模式，若该处用户对象含 `id`）：`frontend/src/pages/TaskDetailPage.tsx`、`frontend/src/pages/ProposalDetailPage.tsx`、`frontend/src/components/TaskTimeline.tsx`、`frontend/src/pages/MessagePage.tsx`
- **不改**：`frontend/src/pages/TaskFormPage.tsx`（那里是选人 picker，不是展示）

> 模式：把 `<Avatar user={x} />` 用 react-router `<Link to={`/u/${x.id}`}>` 包起来。**前提：`x` 必须有 `id` 字段。** 这些嵌套用户对象（`task.assignee` / `p.creator` / `news.author` / 消息对端等）的序列化若已含 `id` 则直接包；若某个缺 `id`，去对应后端序列化器（`tasks/serializers.py` / `news/serializers.py` / `proposals/serializers.py` / `messaging/serializers.py`）给嵌套用户字段补上 `"id"`。

- [ ] **Step 1: NewsDetailPage 作者头像**

确认 `news.author` 含 `id`（查 `news/serializers.py` 中作者嵌套字段；缺则补 `"id"`）。在 `frontend/src/pages/NewsDetailPage.tsx` 顶部 import 加：

```tsx
import { Link } from "react-router-dom";
```

把第 63 行附近：

```tsx
<Avatar user={news.author} size="sm" />
```

改为：

```tsx
<Avatar user={news.author} size="sm" />
```

外层 `<span>`（第 62–65 行那个包住 Avatar + 名字的 span）整体用 `<Link>` 替换，使其可点跳转。具体：找到包含 `<Avatar user={news.author} ... />` 的那个外层元素，把它的标签从 `<span ...>` 改为 `<Link to={`/u/${news.author.id}`} ...>`，闭合标签同步改。若该外层元素同时承担其它布局作用不便替换，则在 `<Avatar>` 外再套一层 `<Link>`：

```tsx
<Link to={`/u/${news.author.id}`}><Avatar user={news.author} size="sm" /></Link>
```

- [ ] **Step 2: ProposalListPage 创建人头像**

在 `frontend/src/pages/ProposalListPage.tsx` 顶部 import 加 `import { Link } from "react-router-dom";`。确认 `p.creator` 含 `id`（查 `proposals/serializers.py`，缺则补）。把第 142 行 `<Avatar user={p.creator} />` 包起来：

```tsx
{p.creator && (
  <Link to={`/u/${p.creator.id}`}>
    <Avatar user={p.creator} />
  </Link>
)}
```

（保留其后 `{p.creator.nickname || p.creator.username}` 文本不变。）

- [ ] **Step 3: TaskListPage 负责人头像**

在 `frontend/src/pages/TaskListPage.tsx` 顶部 import 加 `import { Link } from "react-router-dom";`。确认 `task.assignee` 含 `id`（查 `tasks/serializers.py`，缺则补）。把第 142 行 `{task.assignee && <Avatar user={task.assignee} />}` 改为：

```tsx
{task.assignee && <Link to={`/u/${task.assignee.id}`}><Avatar user={task.assignee} /></Link>}
```

- [ ] **Step 4: 其余展示型头像（同模式）**

对 `TaskDetailPage.tsx`、`ProposalDetailPage.tsx`、`components/TaskTimeline.tsx`、`MessagePage.tsx` 中每个**展示型** `<Avatar user={x} ... />`：

1. 确认 `x.id` 存在（查对应序列化器，缺则补 `"id"`）。
2. import `Link`。
3. 用 `<Link to={`/u/${x.id}`}>` 包住该 `<Avatar>`。

> 排除：`TaskFormPage.tsx`（选人按钮，不是展示）。若某处 `x` 可能为 `null`/`undefined`（如未分配负责人），保持原有的条件渲染 `{x && <Link ...><Avatar .../></Link>}`。

- [ ] **Step 5: 构建确认**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 6: 手动冒烟**

前端跑起来后，在新闻详情、申报列表、任务列表点别人头像 → 跳到 `/u/<该用户id>` 的访客主页。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/pages/NewsDetailPage.tsx frontend/src/pages/ProposalListPage.tsx frontend/src/pages/TaskListPage.tsx frontend/src/pages/TaskDetailPage.tsx frontend/src/pages/ProposalDetailPage.tsx frontend/src/components/TaskTimeline.tsx frontend/src/pages/MessagePage.tsx
# 若改了序列化器，一并 add 对应 apps 的 serializers.py
git commit -m "feat(frontend): 各处展示型头像可点击跳转 /u/<id>"
```

---

## 完成后的整体验收

- [ ] **后端全测试**：`uv run python manage.py test accounts -v 1` 全 PASS。
- [ ] **前端构建**：`cd frontend && npm run build` 成功。
- [ ] **端到端冒烟**：按 Task 9 Step 6 的 7 条逐项确认。
- [ ] **权限边界抽查**：用普通成员账号确认看不到别人的草稿新闻 / 未通过申报 / 任何任务 / 权限 tab。

## Self-Review（plan ↔ spec 覆盖核对）

- **路由 `/u/:id` + `/profile` 重定向 + `?tab=`** → Task 9 ✓
- **身份判定用服务端 `viewer`** → Task 2（后端返回 viewer）+ Task 9（前端读 viewer）✓
- **Tab 矩阵（自己 7 / 别人 2 / 管理员 +权限）** → Task 9 SELF_TABS + tabs 组装 ✓
- **别人看申报只露 approved、任务 403、news 只露 published** → Task 3 ✓
- **Hero（头像/名/角色徽章/注册时间/简介/编辑按钮）** → Task 5 ✓
- **左栏 vs 横向条自适应** → Task 9（isOwner 分支）+ Task 5 CSS media query ✓
- **cobalt 落地 + profile.css** → Task 5 ✓
- **组→色映射（社长/信息组/成员）** → Task 4 ROLE_BADGE + Task 5 CSS ✓
- **后端 2 端点** → Task 2 + Task 3 ✓
- **api/client.ts + types/profile.ts** → Task 4 ✓
- **8 个 profile 子组件** → Task 5–8（Hero/SideNav/Tabs/EditPanel/PasswordPanel/SessionsPanel/ContentListPanel/PermissionsPanel）✓
- **点头像跳转** → Task 10 ✓
- **默认 tab：自己→profile，别人→news** → Task 9 defaultTab ✓
- **边界（404/401/非法 tab 回退/空态/保存同步）** → Task 9 + 各 panel ✓
- **测试（后端 TDD + 前端冒烟）** → Task 1–3 + 各前端 task Step 6 ✓
- **不新增迁移** → 全程未动 models ✓
