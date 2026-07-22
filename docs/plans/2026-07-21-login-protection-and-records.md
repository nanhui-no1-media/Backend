# 登录安全增强 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有单会话挤号基础上，实现①轮询提速 60s→5s、②登录后立即自检防假登录、③登录记录可查（保留历史 + `/auth/sessions/` + 个人中心卡片）、④10 分钟登录保护（保护期内拒绝他方登录、同会话豁免、登出解除）。

**Architecture:** 后端复用 `accounts.UserSession`（无新表/无迁移）：`record_user_session` 改为保留历史并裁剪到每用户 20 条；`login_view` 在认证后加 10 分钟保护门禁；`logout_view` 登出时清 `is_current`；新增 `GET /auth/sessions/`。前端：`shared.ts` 给 Error 挂 `reason/retry_after`；`SessionGuard` 轮询改 5s；`LoginModal` 登录后自检 + 保护期提示；`ProfilePage` 加登录记录卡片。

**Tech Stack:** Python 3.14 / Django 6.0（`uv run python manage.py test accounts`）、React 19 / TS / Webpack（`npx tsc --noEmit`、`npm run build`）。前端无单元测试运行器，靠类型检查 + 构建 + 手动验证。

**设计文档：** `docs/superpowers/specs/2026-07-21-login-protection-and-records-design.md`

**约定：** 后端任务严格 TDD（先写/改测试 → 跑红 → 实现 → 跑绿 → 提交）。提交信息用中文 conventional 风格，结尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。每个提交只含本任务相关文件。

---

## 文件结构

**后端**
- `accounts/utils.py` — `record_user_session` 改为保留历史 + 裁剪；新增常量 `SESSION_HISTORY_LIMIT`。
- `accounts/views.py` — `logout_view` 清 `is_current`；`login_view` 加保护门禁 + 常量 `LOGIN_PROTECTION_SECONDS`；新增 `sessions_view`；导入 `require_GET`、`timezone`、`timedelta`、`UserSession`。
- `accounts/urls.py` — 新增 `sessions/` 路由。
- `accounts/tests.py` — 更新 2 个会变红的旧用例 + 新增 4 组用例。

**前端**
- `frontend/src/api/shared.ts` — Error 挂 `reason` / `retry_after`。
- `frontend/src/api/client.ts` — 新增 `listSessions`。
- `frontend/src/components/SessionGuard.tsx` — 轮询 60s → 5s。
- `frontend/src/components/LoginModal.tsx` — 登录后自检 + 保护期提示。
- `frontend/src/pages/ProfilePage.tsx` — 登录记录卡片。

---

## Task 1: 登录历史保留（`record_user_session`）

**Files:**
- Modify: `accounts/utils.py`
- Test: `accounts/tests.py`（`RecordUserSessionTest`）

- [ ] **Step 1: 更新会变红的旧用例 `test_second_login_supersedes_first`**

旧逻辑二次登录后只剩 1 条（旧行被删）；新逻辑保留历史，故为 2 条、且 `is_current=True` 唯一。打开 `accounts/tests.py`，把 `RecordUserSessionTest.test_second_login_supersedes_first`（约 314–320 行）改为：

```python
    def test_second_login_supersedes_first(self):
        record_user_session(self._req(), self.user, "keyA")
        record_user_session(self._req(), self.user, "keyB")
        # 历史保留：两行都在；is_current 仅 keyB
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 2)
        current = UserSession.objects.get(user=self.user, is_current=True)
        self.assertEqual(current.session_key, "keyB")
```

- [ ] **Step 2: 新增裁剪测试（先写，让它因尚未裁剪到 20 而失败）**

在 `RecordUserSessionTest` 末尾（`test_same_key_updates_in_place` 之后）加：

```python
    def test_history_pruned_to_limit(self):
        # 制造 25 次登录：保留最近 20 条，最旧的被裁掉
        for i in range(25):
            record_user_session(self._req(), self.user, f"key{i:02d}")
        rows = list(UserSession.objects.filter(user=self.user).order_by("created_at", "id"))
        self.assertLessEqual(len(rows), 20, "应裁剪到不超过 20 条")
        # 当前会话（最后一次 key24）必在保留之列且为 current
        current = UserSession.objects.get(user=self.user, is_current=True)
        self.assertEqual(current.session_key, "key24")
        self.assertIn(current.id, [r.id for r in rows])
```

- [ ] **Step 3: 跑测试，确认新测试失败**

Run: `uv run python manage.py test accounts.RecordUserSessionTest`
Expected: `test_history_pruned_to_limit` FAIL（当前实现删除所有非 current 行，25 次登录后只剩 1 条；`test_second_login_supersedes_first` 也因 count==2 而 FAIL）。其余 RecordUserSessionTest 用例仍 PASS。

- [ ] **Step 4: 实现——保留历史并裁剪**

打开 `accounts/utils.py`。在文件顶部常量区（`_BOT_RE` 等正则之前）加：

```python
SESSION_HISTORY_LIMIT = 20  # 每用户保留的登录记录条数（含当前会话）
```

把 `record_user_session` 末尾的删除行：

```python
    UserSession.objects.filter(user=user, is_current=False).delete()
```

替换为裁剪到最近 N 条：

```python
    # 保留登录历史：不再删除旧会话，仅裁剪到每用户最近 SESSION_HISTORY_LIMIT 条
    keep_ids = list(
        UserSession.objects.filter(user=user)
        .order_by("-created_at", "-id")[:SESSION_HISTORY_LIMIT]
        .values_list("id", flat=True)
    )
    UserSession.objects.filter(user=user).exclude(id__in=keep_ids).delete()
```

- [ ] **Step 5: 跑测试，确认全绿**

Run: `uv run python manage.py test accounts.RecordUserSessionTest`
Expected: PASS（4 个用例全过）。

- [ ] **Step 6: 提交**

```bash
git add accounts/utils.py accounts/tests.py
git commit -m "feat(accounts): 登录历史保留——record_user_session 不再删旧会话，裁剪到每用户最近 20 条" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 登出清理当前会话（`logout_view`）

为 10 分钟保护的"主动登出即解保护"铺路。现状 `logout_view` 只 `flush()` 会话，不动 `UserSession`。

**Files:**
- Modify: `accounts/views.py:68-72`
- Test: `accounts/tests.py`（`LogoutViewTest`）

- [ ] **Step 1: 写失败测试**

`accounts/tests.py` 顶部已 `from .models import UserSession`。在 `LogoutViewTest` 类末尾（`test_logout_unauthenticated` 之后）加：

```python
    def test_logout_clears_current_session_row(self):
        self.client.login(username="testuser", password="secret123")
        self.assertTrue(UserSession.objects.filter(user=self.user, is_current=True).exists())
        self.client.post("/auth/logout/")
        self.assertFalse(UserSession.objects.filter(user=self.user, is_current=True).exists())
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `uv run python manage.py test accounts.LogoutViewTest.test_logout_clears_current_session_row`
Expected: FAIL（登出后 `is_current=True` 行仍存在）。

- [ ] **Step 3: 实现——登出前置 `is_current=False`**

打开 `accounts/views.py`。把 `from .models import Profile`（第 15 行）改为同时导入 `UserSession`：

```python
from .models import Profile, UserSession
```

把 `logout_view`（68–72 行）整体替换为（在 `auth_logout` 之前捕获用户，因 `auth_logout` 会把 `request.user` 置为匿名）：

```python
@require_POST
@login_required
def logout_view(request):
    user = request.user
    auth_logout(request)
    UserSession.objects.filter(user=user, is_current=True).update(is_current=False)
    return JsonResponse({"message": "Logged out"})
```

- [ ] **Step 4: 跑测试，确认全绿**

Run: `uv run python manage.py test accounts.LogoutViewTest`
Expected: PASS（3 个用例全过）。

- [ ] **Step 5: 提交**

```bash
git add accounts/views.py accounts/tests.py
git commit -m "fix(accounts): logout 清理 UserSession.is_current，为登录保护解除铺路" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 10 分钟登录保护（`login_view`）

**Files:**
- Modify: `accounts/views.py:34-53`
- Test: `accounts/tests.py`（更新 `SingleSessionMiddlewareTest` + 新增 `LoginProtectionTest`）

- [ ] **Step 1: 更新会被保护逻辑改红的旧用例 `test_superseded_device_gets_401_with_takeover`**

该用例（约 375–390 行）让 a 用 `Client.login()` 登录后，b 立刻 POST 登录挤掉 a。加了保护后，b 的登录会被 409 拒绝、a 不会被挤，断言 401 会失败。需先把 a 的当前会话"老化"到 10 分钟外。在 `accounts/tests.py` 顶部导入区加（若已有则跳过）：

```python
from datetime import timedelta
from django.utils import timezone
```

把 `SingleSessionMiddlewareTest.test_superseded_device_gets_401_with_takeover` 整体替换为：

```python
    def test_superseded_device_gets_401_with_takeover(self):
        a = self._login()
        # 老化 a 的当前会话到保护期外（≥10 分钟），b 才能挤号
        UserSession.objects.filter(user=self.user, is_current=True).update(
            created_at=timezone.now() - timedelta(minutes=11)
        )
        b = Client()
        b.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "secret123"}),
            content_type="application/json",
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148 Safari",
        )
        resp = a.get("/auth/me/")
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertEqual(data["reason"], "session_superseded")
        self.assertEqual(data["takeover"]["device_type"], "Mobile")
        self.assertIn("iOS", data["takeover"]["device_name"])
        self.assertIn("time", data["takeover"])
```

- [ ] **Step 2: 跑该用例，确认仍绿（保护尚未实现，老化不影响旧逻辑）**

Run: `uv run python manage.py test accounts.SingleSessionMiddlewareTest.test_superseded_device_gets_401_with_takeover`
Expected: PASS。

- [ ] **Step 3: 新增 `LoginProtectionTest`（先写，让其因无保护而失败）**

在 `accounts/tests.py` 末尾追加整个新类：

```python
class LoginProtectionTest(TestCase):
    """10 分钟登录保护：登录后 10 分钟内，他方新会话登录该账号被拒绝。"""
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@e.com", password="secret123")

    def _post_login(self, client, **extra):
        return client.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "secret123"}),
            content_type="application/json",
            **extra,
        )

    def test_second_login_within_window_is_blocked(self):
        a = Client()
        a.login(username="u", password="secret123")  # 建立当前会话（age≈0）
        b = Client()
        resp = self._post_login(b)
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data["reason"], "login_protection")
        self.assertGreater(data["retry_after"], 0)
        # a 仍是当前会话、可继续访问
        self.assertTrue(UserSession.objects.filter(user=self.user, is_current=True).count(), 1)
        self.assertEqual(a.get("/auth/me/").status_code, 200)

    def test_second_login_after_window_is_allowed(self):
        a = Client()
        a.login(username="u", password="secret123")
        UserSession.objects.filter(user=self.user, is_current=True).update(
            created_at=timezone.now() - timedelta(minutes=11)
        )
        b = Client()
        resp = self._post_login(b)
        self.assertEqual(resp.status_code, 200)
        # a 现已被挤下线
        self.assertEqual(a.get("/auth/me/").status_code, 401)

    def test_logout_releases_protection(self):
        a = Client()
        a.login(username="u", password="secret123")
        a.post("/auth/logout/")  # 主动登出 → 清 is_current（依赖 Task 2）
        b = Client()
        resp = self._post_login(b)
        self.assertEqual(resp.status_code, 200)

    def test_same_session_reauth_is_exempt(self):
        c = Client()
        c.login(username="u", password="secret123")  # 当前会话 = c 的 session_key
        # 同一 client（同一 session_key）再次提交登录 → 不拦截
        resp = self._post_login(c)
        self.assertEqual(resp.status_code, 200)

    def test_wrong_password_not_treated_as_protection(self):
        a = Client()
        a.login(username="u", password="secret123")
        b = Client()
        resp = b.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertNotEqual(resp.json().get("reason"), "login_protection")
```

- [ ] **Step 4: 跑新测试，确认失败**

Run: `uv run python manage.py test accounts.LoginProtectionTest`
Expected: 除 `test_wrong_password_not_treated_as_protection` 外均 FAIL（无保护逻辑，b 的登录直接 200 挤掉 a）。

- [ ] **Step 5: 实现——`login_view` 加保护门禁**

打开 `accounts/views.py`。把第 5 行的导入：

```python
from django.views.decorators.http import require_POST
```

改为（新增 `timedelta`、`timezone`，保护门禁要用）：

```python
from datetime import timedelta
from django.views.decorators.http import require_POST
from django.utils import timezone
```

在 `from .forms import ...`（第 14 行）下方、`LOGIN_PROTECTION_SECONDS` 使用前，于模块顶部（`_json_body` 之前）加常量：

```python
LOGIN_PROTECTION_SECONDS = 600  # 登录保护窗口：登录后 10 分钟内他方新会话登录被拒
```

把 `login_view`（34–53 行）整体替换为：

```python
@require_POST
def login_view(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = LoginForm(body)
    if not form.is_valid():
        return JsonResponse({"error": _form_errors(form)}, status=400)

    username = form.get_username()
    if username is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    user = authenticate(request, username=username, password=form.cleaned_data["password"])
    if user is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    # 10 分钟登录保护：该账号已有当前会话且登录未满窗口、且非同一会话再认证 → 拒绝
    existing = UserSession.objects.filter(user=user, is_current=True).first()
    if existing:
        age = timezone.now() - existing.created_at
        same_session = existing.session_key == request.session.session_key
        if not same_session and age < timedelta(seconds=LOGIN_PROTECTION_SECONDS):
            retry_after = max(0, int(LOGIN_PROTECTION_SECONDS - age.total_seconds()))
            return JsonResponse(
                {
                    "error": "Login protection active",
                    "reason": "login_protection",
                    "retry_after": retry_after,
                },
                status=409,
            )

    login(request, user)
    return JsonResponse({"user": {"id": user.id, "username": user.username, "email": user.email}})
```

- [ ] **Step 6: 跑保护 + 中间件相关测试，确认全绿**

Run: `uv run python manage.py test accounts.LoginProtectionTest accounts.SingleSessionMiddlewareTest`
Expected: PASS（保护 5 个 + 中间件 5 个用例全过）。

- [ ] **Step 7: 跑整个 accounts 套件，确认无回归**

Run: `uv run python manage.py test accounts`
Expected: 全部 PASS（含已更新的两个旧用例）。

- [ ] **Step 8: 提交**

```bash
git add accounts/views.py accounts/tests.py
git commit -m "feat(accounts): 10 分钟登录保护——保护期内拒绝他方新会话登录，同会话/登出豁免" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 登录记录接口（`GET /auth/sessions/`）

**Files:**
- Modify: `accounts/views.py`（新增 `sessions_view`）、`accounts/urls.py`
- Test: `accounts/tests.py`（新增 `SessionsViewTest`）

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 末尾追加：

```python
class SessionsViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="secret123")
        self.factory = RequestFactory()

    def _seed(self, n):
        for i in range(n):
            record_user_session(
                self.factory.get("/", REMOTE_ADDR="1.2.3.4"),
                self.user,
                f"key{i:02d}",
            )

    def test_returns_own_sessions(self):
        c = Client()
        c.login(username="u", password="secret123")
        resp = c.get("/auth/sessions/")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertGreaterEqual(len(results), 1)
        row = results[0]
        for key in ("id", "device_name", "device_type", "ip_address", "created_at", "is_current"):
            self.assertIn(key, row)

    def test_limited_and_newest_first(self):
        self._seed(25)  # 每次调用 record_user_session 都裁剪到 20
        c = Client()
        c.login(username="u", password="secret123")  # 再加 1 条当前会话
        results = c.get("/auth/sessions/").json()["results"]
        self.assertEqual(len(results), 20)
        self.assertTrue(results[0]["is_current"])  # 最新（当前）排首位

    def test_anonymous_redirected(self):
        self.assertEqual(Client().get("/auth/sessions/").status_code, 302)
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `uv run python manage.py test accounts.SessionsViewTest`
Expected: FAIL（路由不存在 → 404/None）。

- [ ] **Step 3: 实现——新增 `sessions_view`**

打开 `accounts/views.py`，在 `me_view` 之后（约 79 行后）插入：

```python
@require_GET
@login_required
def sessions_view(request):
    """当前用户最近登录记录（设备/IP/时间），用于个人中心"登录记录"。"""
    rows = (
        UserSession.objects.filter(user=request.user)
        .order_by("-created_at", "-id")[:SESSION_HISTORY_LIMIT]
    )
    return JsonResponse({
        "results": [
            {
                "id": r.id,
                "device_name": r.device_name,
                "device_type": r.device_type,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat(),
                "is_current": r.is_current,
            }
            for r in rows
        ]
    })
```

`sessions_view` 用到 `require_GET`、`SESSION_HISTORY_LIMIT`、`UserSession`。`UserSession` 已在 Task 2 导入。还需补两处导入：

1) 把第 5 行（Task 3 改过的）导入行：

```python
from django.views.decorators.http import require_POST
```

改为：

```python
from django.views.decorators.http import require_POST, require_GET
```

2) 在模型导入行 `from .models import Profile, UserSession` 下方加一行：

```python
from .utils import SESSION_HISTORY_LIMIT
```

- [ ] **Step 4: 加路由**

打开 `accounts/urls.py`，在 `urlpatterns` 里 `me/` 之后加一行：

```python
    path("sessions/", views.sessions_view, name="sessions"),
```

完整文件应为：

```python
from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.me_view, name="me"),
    path("sessions/", views.sessions_view, name="sessions"),
    path("csrf/", views.csrf_token_view, name="csrf_token"),
    path("password-reset/", views.password_reset_view, name="password_reset"),
    path("password-reset/confirm/", views.password_reset_confirm_view, name="password_reset_confirm"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/update/", views.profile_update_view, name="profile_update"),
    path("profile/change-password/", views.change_password_view, name="change_password"),
    path("users/", views.users_view, name="users"),
]
```

- [ ] **Step 5: 跑测试，确认全绿**

Run: `uv run python manage.py test accounts.SessionsViewTest`
Expected: PASS（3 个用例全过）。

- [ ] **Step 6: 提交**

```bash
git add accounts/views.py accounts/urls.py accounts/tests.py
git commit -m "feat(accounts): GET /auth/sessions/ 返回最近登录记录供个人中心展示" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 前端 API 层（`shared.ts` + `client.ts`）

**Files:**
- Modify: `frontend/src/api/shared.ts:45-49`、`frontend/src/api/client.ts`

- [ ] **Step 1: `shared.ts` 给 Error 挂 `reason` / `retry_after`**

打开 `frontend/src/api/shared.ts`，把 `if (!res.ok)` 分支：

```ts
    if (!res.ok) {
      const err = new Error(data.detail || data.error || "请求失败") as Error & { status: number };
      err.status = res.status;
      throw err;
    }
```

替换为：

```ts
    if (!res.ok) {
      const err = new Error(data.detail || data.error || "请求失败") as Error & {
        status: number;
        reason?: string;
        retry_after?: number;
      };
      err.status = res.status;
      err.reason = data?.reason;
      if (typeof data?.retry_after === "number") err.retry_after = data.retry_after;
      throw err;
    }
```

- [ ] **Step 2: `client.ts` 新增 `listSessions`**

打开 `frontend/src/api/client.ts`，在 `me:` 之后加一项：

```ts
  me: () =>
    request("/me/"),

  listSessions: () =>
    request("/sessions/"),
```

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出（无错误）。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/shared.ts frontend/src/api/client.ts
git commit -m "feat(api): shared Error 挂 reason/retry_after；client 新增 listSessions" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 轮询提速（`SessionGuard` 60s → 5s）

**Files:**
- Modify: `frontend/src/components/SessionGuard.tsx:8`

- [ ] **Step 1: 改轮询间隔**

打开 `frontend/src/components/SessionGuard.tsx`，把第 8 行：

```ts
const POLL_INTERVAL_MS = 60000;
```

改为：

```ts
// 被挤设备最迟 ~5s 感知（原 60s）。内部工具并发低，5s 心跳可接受。
const POLL_INTERVAL_MS = 5000;
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/SessionGuard.tsx
git commit -m "feat(session): 挤号轮询 60s→5s，提升异地登录感知灵敏度" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 登录后自检 + 保护期提示（`LoginModal`）

**Files:**
- Modify: `frontend/src/components/LoginModal.tsx`（`handleSubmit`）

- [ ] **Step 1: 改 `handleSubmit`——登录后自检 + 保护期分支**

打开 `frontend/src/components/LoginModal.tsx`，把整个 `handleSubmit`（约 37–56 行；文件顶部已有 `LOGIN_ERROR_ZH` 映射）替换为：

```tsx
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!account.trim() || !password) {
      setError("请填写账号与密码后再登录。");
      return;
    }
    setLoading(true);
    try {
      if (method === "username") await api.login(account.trim(), password);
      else await api.loginWithEmail(account.trim(), password);

      // 防假登录：立即自检刚建立的会话；若已被挤/未真正建立，不进入"已登录"假态
      try {
        await api.me();
      } catch (selfErr: any) {
        if (selfErr?.status === 401) {
          // supersede 弹窗已由 shared.ts 拦截器 + SessionGuard 触发
          onClose();
          return;
        }
        // 其它错误（网络等）：登录确已成功，乐观放行
      }

      onLoggedIn();
      onClose();
      navigate(redirectTo ?? "/");
    } catch (err: any) {
      if (err?.reason === "login_protection") {
        const mins = err.retry_after ? Math.ceil(err.retry_after / 60) : null;
        setError(
          "该账号 10 分钟内在其他设备登录过，处于登录保护期，请稍后重试或由原设备退出登录。" +
            (mins ? `（约 ${mins} 分钟后可重试）` : ""),
        );
        return;
      }
      const raw = err?.message || "";
      setError(LOGIN_ERROR_ZH[raw] || raw || "登录失败，请重试。");
    } finally {
      setLoading(false);
    }
  };
```

> 说明：`onClose` / `onLoggedIn` / `navigate` / `api` / `LOGIN_ERROR_ZH` / `method` / `account` / `password` 均为组件已有作用域内变量，无需新增导入。

- [ ] **Step 2: 类型检查 + 构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/LoginModal.tsx
git commit -m "feat(login): 登录后立即自检防假登录；登录保护期(409)给出中文提示与倒计时" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 个人中心登录记录卡片（`ProfilePage`）

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

- [ ] **Step 1: 加类型与状态**

打开 `frontend/src/pages/ProfilePage.tsx`。在 `interface ProfileData {...}`（8–17 行）之后加：

```tsx
interface SessionRow {
  id: number;
  device_name: string;
  device_type: string;
  ip_address: string | null;
  created_at: string;
  is_current: boolean;
}
```

在组件内现有 `useState` 区（`passwordSaving` 那行之后，约 51 行）加：

```tsx
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
```

- [ ] **Step 2: 加拉取 effect**

在现有 `useEffect`（约 53–65 行，拉 profile 的）之后再加一个：

```tsx
  useEffect(() => {
    api
      .listSessions()
      .then((data: any) => setSessions(data.results || []))
      .catch(() => {})
      .finally(() => setSessionsLoading(false));
  }, []);
```

- [ ] **Step 3: 渲染卡片——在 `form-card` 关闭后、`container` 关闭前插入**

找到修改密码 `collapse` 结束后的 `</div>`（关闭 `form-card`，约 320 行）。在该 `</div>` 之后、关闭 `container` 的 `</div>`（约 321 行）之前，插入：

```tsx
          <div className="card card-pad" style={{ marginTop: "var(--s-5)" }}>
            <h2 style={{ margin: "0 0 var(--s-4)", fontSize: 18 }}>登录记录</h2>
            {sessionsLoading ? (
              <p className="muted">加载中…</p>
            ) : sessions.length === 0 ? (
              <p className="muted">暂无记录</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "var(--s-2)" }}>
                {sessions.map((s) => (
                  <li
                    key={s.id}
                    className="field-value"
                    style={{ display: "flex", justifyContent: "space-between", gap: "var(--s-3)" }}
                  >
                    <span>
                      {s.is_current ? "【当前】" : ""}
                      {s.device_name || s.device_type || "未知设备"}
                      {s.ip_address ? ` · IP ${s.ip_address}` : ""}
                    </span>
                    <span className="muted">{new Date(s.created_at).toLocaleString("zh-CN")}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
```

> 结构核对：外层 `<div className="container" ...>` 内现有 `<div className="form-card">…</div>`；新卡片是其兄弟，紧跟在 `form-card` 之后。`card` / `card-pad` / `field-value` / `muted` 均为该页已在用的类。

- [ ] **Step 4: 类型检查 + 构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出。

Run: `cd frontend && npm run build`
Expected: 构建成功，产出 `frontend/dist/`。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/ProfilePage.tsx
git commit -m "feat(profile): 个人中心新增「登录记录」卡片，展示最近登录设备/IP/时间" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 全量验证

- [ ] **Step 1: 后端全套测试**

Run: `uv run python manage.py test accounts`
Expected: 全部 PASS（含 Task 1–4 更新/新增的所有用例）。

- [ ] **Step 2: Django 配置自检**

Run: `uv run python manage.py check`
Expected: 无问题。

- [ ] **Step 3: 前端类型 + 构建**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 均无错误。

- [ ] **Step 4: 手动验证（双浏览器）**

启动后端 `uv run python manage.py runserver` 与前端 `cd frontend && npm run dev`，然后：

1. **保护期拒绝**：浏览器 A 登录账号 → 浏览器 B（无痕）10 分钟内同账号登录 → B 登录框显示"该账号 10 分钟内在其他设备登录过…（约 X 分钟后可重试）"；A 不受影响、可继续操作。
2. **轮询灵敏度**：把 A 的当前会话老化（或满 10 分钟后）让 B 登录成功 → A 在约 5s 内弹出挤号窗（含 B 设备/IP/时间）。
3. **登出解除**：A 主动登出 → B 立刻登录成功（不再被保护拒绝）。
4. **防假登录**：A 登录后，立刻在另一处把 A 挤掉 → A 不进入假登录首页，直接弹挤号窗（自检 401 命中）。
5. **登录记录**：个人中心底部"登录记录"卡片列出近期登录，当前会话标【当前】。
6. **同浏览器再认证**：已登录状态下同浏览器再次提交登录 → 不被保护拦截（200）。

- [ ] **Step 5（可选）: 若手动验证全过，提交收尾说明（无代码改动则跳过）**

无需提交；若验证中发现需微调文案/样式，按需补充提交。

---

## 自检（writing-plans 内置）

- **Spec 覆盖**：①轮询→Task 6；②自检→Task 7；③记录(后端保留→Task 1、接口→Task 4、前端卡片→Task 8)；④保护→Task 3（登出解除依赖→Task 2）；Error 增强→Task 5；登出清理→Task 2。✓ 全覆盖。
- **占位符扫描**：无 TBD/TODO；每个代码步骤均含完整代码。✓
- **类型一致性**：`SESSION_HISTORY_LIMIT`（utils 定义，views 导入）、`LOGIN_PROTECTION_SECONDS`（views 定义）、`listSessions`（client 定义，ProfilePage 调用）、`reason`/`retry_after`（shared 挂载，LoginModal 读取）、`sessions_view`（views 定义，urls 路由）。命名前后一致。✓
