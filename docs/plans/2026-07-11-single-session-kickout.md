# 单会话强制下线（跨设备挤号）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 同一账号在新设备登录后，原设备下一次请求（或 ≤60s 轮询）即被中间件以 401 挤下线，前端弹出带新设备信息的阻塞式弹窗，点"重新登录"回到登录页。

**Architecture:** 后端新增 `UserSession` 模型，每次登录由 `user_logged_in` 信号记录一条"当前会话"（含 IP/UA/设备类型）；`SingleSessionMiddleware` 在每个已登录请求校验"本会话是否仍是该账号最新的"，否则 `flush()` 并返回带 `takeover` 信息的 401。前端在请求收口 `shared.ts` 拦截 `reason=session_superseded` 的 401，由 `SessionGuard`（含 60s 轮询）弹出模态框。

**Tech Stack:** Django 6.0 + DRF（会话认证）、Django `TestCase`/`Client` 测试、React 19 + TS（无前端测试运行器，前端靠 `npm run build` 编译校验 + 手动验证）。

参考设计文档：`docs/superpowers/specs/2026-07-11-single-session-kickout-design.md`（已提交）。

---

## 文件结构

**后端**
| 文件 | 责任 | 动作 |
|---|---|---|
| `accounts/models.py` | 新增 `UserSession` 模型 | 修改 |
| `accounts/migrations/0XXX_add_usersession.py` | 模型迁移 | 由 `makemigrations` 生成 |
| `accounts/utils.py` | `get_client_ip` / `parse_user_agent` / `record_user_session` | 新建 |
| `accounts/signals.py` | `user_logged_in` 信号 → 记录会话 | 新建 |
| `accounts/apps.py` | `ready()` 连接信号 | 修改 |
| `accounts/middleware.py` | `SingleSessionMiddleware` | 新建 |
| `config/settings.py` | 注册中间件 | 修改 |
| `accounts/tests.py` | 各组件单元/集成测试 | 修改 |

**前端**
| 文件 | 责任 | 动作 |
|---|---|---|
| `frontend/src/api/shared.ts` | 401 + `session_superseded` 拦截、`setSupersedeHandler` | 修改 |
| `frontend/src/components/SessionSupersedeModal.tsx` | 阻塞式弹窗 | 新建 |
| `frontend/src/components/SessionGuard.tsx` | 注册回调 + 60s 轮询 + 渲染弹窗 | 新建 |
| `frontend/src/App.tsx` | 挂载 `SessionGuard` | 修改 |

---

## Task 1: `UserSession` 模型 + 迁移

**Files:**
- Modify: `accounts/models.py`
- Modify: `accounts/tests.py`
- Create: `accounts/migrations/0XXX_add_usersession.py`（由命令生成）

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 顶部 import 区追加 `UserSession`，并新增测试类：

```python
# 在文件顶部 import 之后补一行：
from .models import UserSession
```

在文件末尾追加：

```python
class UserSessionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_create_session_defaults(self):
        s = UserSession.objects.create(user=self.user, session_key="abc")
        self.assertTrue(s.is_current)
        self.assertEqual(s.device_type, "Unknown")
        self.assertEqual(s.device_name, "")

    def test_str_contains_username(self):
        s = UserSession.objects.create(user=self.user, session_key="abcdef0123456789")
        self.assertIn("u", str(s))
```

- [ ] **Step 2: 运行测试确认失败**

运行：`uv run python manage.py test accounts.tests.UserSessionModelTest`
预期：FAIL（`ImportError: cannot import name 'UserSession'`）。

- [ ] **Step 3: 实现模型**

在 `accounts/models.py` 末尾（`Profile` 类之后）追加：

```python
class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_sessions")
    session_key = models.CharField(max_length=40, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    device_type = models.CharField(max_length=16, default="Unknown")
    device_name = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["user", "is_current"])]
        ordering = ["-created_at"]

    def __str__(self):
        state = "current" if self.is_current else "old"
        return f"{self.user.username} @ {self.session_key[:8]} ({state})"
```

- [ ] **Step 4: 生成并应用迁移**

运行：
```bash
uv run python manage.py makemigrations accounts
uv run python manage.py migrate
```
预期：`makemigrations` 输出 `Create model UserSession`，生成 `accounts/migrations/0XXX_add_usersession.py`；`migrate` 输出 `Applying accounts.0XXX_add_usersession... OK`。

- [ ] **Step 5: 运行测试确认通过**

运行：`uv run python manage.py test accounts.tests.UserSessionModelTest`
预期：OK（2 个测试通过）。

- [ ] **Step 6: 提交**

```bash
git add accounts/models.py accounts/migrations/ accounts/tests.py
git commit -m "feat(accounts): 新增 UserSession 模型记录登录会话" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `accounts/utils.py`（IP/UA 解析 + 记录会话）

**Files:**
- Create: `accounts/utils.py`
- Modify: `accounts/tests.py`

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 顶部 import 区追加：

```python
from django.test import RequestFactory
from .utils import get_client_ip, parse_user_agent, record_user_session
```

在文件末尾追加：

```python
class ParseUserAgentTest(TestCase):
    def test_desktop_chrome_windows(self):
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        dtype, dname = parse_user_agent(ua)
        self.assertEqual(dtype, "Desktop")
        self.assertIn("Chrome", dname)
        self.assertIn("Windows", dname)

    def test_mobile_iphone(self):
        ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
              "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1")
        dtype, dname = parse_user_agent(ua)
        self.assertEqual(dtype, "Mobile")
        self.assertIn("iOS", dname)

    def test_tablet_ipad(self):
        ua = ("Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
        dtype, _ = parse_user_agent(ua)
        self.assertEqual(dtype, "Tablet")

    def test_bot(self):
        dtype, _ = parse_user_agent("Mozilla/5.0 (compatible; Googlebot/2.1; +http://google.com/bot.html)")
        self.assertEqual(dtype, "Bot")

    def test_empty(self):
        self.assertEqual(parse_user_agent(""), ("Unknown", ""))


class GetClientIpTest(TestCase):
    def test_remote_addr(self):
        req = RequestFactory().get("/", REMOTE_ADDR="1.2.3.4")
        self.assertEqual(get_client_ip(req), "1.2.3.4")


class RecordUserSessionTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="u", password="p")

    def _req(self):
        return self.factory.get(
            "/",
            REMOTE_ADDR="9.9.9.9",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0",
        )

    def test_creates_current_row(self):
        record_user_session(self._req(), self.user, "keyA")
        s = UserSession.objects.get(session_key="keyA")
        self.assertTrue(s.is_current)
        self.assertEqual(s.ip_address, "9.9.9.9")
        self.assertEqual(s.device_type, "Desktop")

    def test_second_login_supersedes_first(self):
        record_user_session(self._req(), self.user, "keyA")
        record_user_session(self._req(), self.user, "keyB")
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)
        current = UserSession.objects.get(user=self.user)
        self.assertEqual(current.session_key, "keyB")
        self.assertTrue(current.is_current)

    def test_same_key_updates_in_place(self):
        record_user_session(self._req(), self.user, "keyA")
        record_user_session(self._req(), self.user, "keyA")
        self.assertEqual(UserSession.objects.filter(session_key="keyA").count(), 1)
        self.assertTrue(UserSession.objects.get(session_key="keyA").is_current)
```

- [ ] **Step 2: 运行测试确认失败**

运行：`uv run python manage.py test accounts.tests.ParseUserAgentTest accounts.tests.GetClientIpTest accounts.tests.RecordUserSessionTest`
预期：FAIL（`ModuleNotFoundError: No module named 'accounts.utils'`）。

- [ ] **Step 3: 实现 `accounts/utils.py`**

新建 `accounts/utils.py`：

```python
import re

from django.db import transaction

from .models import UserSession


_BOT_RE = re.compile(r"bot|crawl|spider|slurp|fetcher", re.I)
_TABLET_RE = re.compile(r"iPad|Android(?!.*Mobile)|Silk|Kindle|PlayBook", re.I)
_MOBILE_RE = re.compile(r"Android|iPhone|iPod|Mobile|Windows Phone|BlackBerry", re.I)
_BROWSER_RE = re.compile(r"(Edge|Edg|OPR|Opera|Chrome|Chromium|Firefox|Safari|MSIE|Trident)[/ ]([\d.]+)")
_OS_RE = re.compile(r"(Windows NT|Windows \w+|Mac OS X|iPhone OS|Android|Linux)")


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR")


def parse_user_agent(ua):
    if not ua:
        return "Unknown", ""
    if _BOT_RE.search(ua):
        device_type = "Bot"
    elif _TABLET_RE.search(ua):
        device_type = "Tablet"
    elif _MOBILE_RE.search(ua):
        device_type = "Mobile"
    else:
        device_type = "Desktop"

    browser = ""
    m = _BROWSER_RE.search(ua)
    if m:
        name = {"Edg": "Edge", "OPR": "Opera", "MSIE": "IE", "Trident": "IE"}.get(m.group(1), m.group(1))
        browser = name

    os_name = ""
    o = _OS_RE.search(ua)
    if o:
        raw = o.group(1)
        if raw.startswith("Windows"):
            os_name = "Windows"
        elif raw.startswith("Mac OS X"):
            os_name = "macOS"
        elif raw.startswith("iPhone OS"):
            os_name = "iOS"
        elif raw.startswith("Android"):
            os_name = "Android"
        elif raw.startswith("Linux"):
            os_name = "Linux"
        else:
            os_name = raw

    device_name = " · ".join(p for p in (browser, os_name) if p)
    return device_type, device_name


@transaction.atomic
def record_user_session(request, user, session_key):
    ip = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")
    device_type, device_name = parse_user_agent(ua)

    UserSession.objects.filter(user=user).update(is_current=False)
    UserSession.objects.update_or_create(
        session_key=session_key,
        defaults={
            "user": user,
            "ip_address": ip,
            "user_agent": ua,
            "device_type": device_type,
            "device_name": device_name,
            "is_current": True,
        },
    )
    UserSession.objects.filter(user=user, is_current=False).delete()
```

- [ ] **Step 4: 运行测试确认通过**

运行：`uv run python manage.py test accounts.tests.ParseUserAgentTest accounts.tests.GetClientIpTest accounts.tests.RecordUserSessionTest`
预期：OK（全部通过）。

- [ ] **Step 5: 提交**

```bash
git add accounts/utils.py accounts/tests.py
git commit -m "feat(accounts): 新增 UA/IP 解析与会话记录工具" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `user_logged_in` 信号接入

**Files:**
- Create: `accounts/signals.py`
- Modify: `accounts/apps.py`
- Modify: `accounts/tests.py`

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 末尾追加（用两个独立 `Client` 模拟两台设备）：

```python
class LoginSignalIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@e.com", password="secret123")

    def test_login_creates_user_session(self):
        c = Client()
        c.login(username="u", password="secret123")
        s = UserSession.objects.get(user=self.user)
        self.assertTrue(s.is_current)
        self.assertTrue(s.session_key)

    def test_login_records_device_info(self):
        c = Client()
        c.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "secret123"}),
            content_type="application/json",
            REMOTE_ADDR="1.2.3.4",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0",
        )
        s = UserSession.objects.get(user=self.user)
        self.assertEqual(s.ip_address, "1.2.3.4")
        self.assertEqual(s.device_type, "Desktop")
        self.assertIn("Chrome", s.device_name)

    def test_second_device_login_leaves_single_current_row(self):
        a = Client()
        a.login(username="u", password="secret123")
        b = Client()
        b.login(username="u", password="secret123")
        self.assertEqual(UserSession.objects.filter(user=self.user, is_current=True).count(), 1)
```

- [ ] **Step 2: 运行测试确认失败**

运行：`uv run python manage.py test accounts.tests.LoginSignalIntegrationTest`
预期：FAIL（`UserSession matching query does not exist`，因为信号尚未连接）。

- [ ] **Step 3: 实现信号**

新建 `accounts/signals.py`：

```python
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .utils import record_user_session


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    session_key = request.session.session_key
    if session_key:
        record_user_session(request, user, session_key)
```

修改 `accounts/apps.py` 为：

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        from . import signals  # noqa: F401
```

- [ ] **Step 4: 运行测试确认通过**

运行：`uv run python manage.py test accounts.tests.LoginSignalIntegrationTest`
预期：OK（3 个测试通过）。

- [ ] **Step 5: 回归现有登录测试**

运行：`uv run python manage.py test accounts`
预期：OK（全部既有测试 + 新增测试通过，登录响应仍是 200、未登录访问仍是 302）。

- [ ] **Step 6: 提交**

```bash
git add accounts/signals.py accounts/apps.py accounts/tests.py
git commit -m "feat(accounts): user_logged_in 信号记录登录会话" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `SingleSessionMiddleware` 强制挤下线

**Files:**
- Create: `accounts/middleware.py`
- Modify: `config/settings.py`
- Modify: `accounts/tests.py`

- [ ] **Step 1: 写失败测试**

在 `accounts/tests.py` 末尾追加：

```python
class SingleSessionMiddlewareTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@e.com", password="secret123")

    def _login(self):
        c = Client()
        c.login(username="u", password="secret123")
        return c

    def test_first_device_can_access(self):
        a = self._login()
        self.assertEqual(a.get("/auth/me/").status_code, 200)

    def test_superseded_device_gets_401_with_takeover(self):
        a = self._login()
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

    def test_new_device_can_access_after_takeover(self):
        a = self._login()
        b = self._login()
        self.assertEqual(b.get("/auth/me/").status_code, 200)

    def test_anonymous_request_passes_through(self):
        # /auth/me/ 是 login_required，匿名应得到 302（而非中间件 500）
        self.assertEqual(Client().get("/auth/me/").status_code, 302)

    def test_pre_feature_session_is_adopted(self):
        a = self._login()
        UserSession.objects.all().delete()  # 模拟上线前已存在的会话
        self.assertEqual(a.get("/auth/me/").status_code, 200)
        self.assertTrue(UserSession.objects.filter(user=self.user, is_current=True).exists())
```

- [ ] **Step 2: 运行测试确认失败**

运行：`uv run python manage.py test accounts.tests.SingleSessionMiddlewareTest`
预期：FAIL（`test_superseded_device_gets_401_with_takeover` 拿到 200，因为中间件尚未实现；`test_pre_feature_session_is_adopted` 也失败）。

- [ ] **Step 3: 实现中间件**

新建 `accounts/middleware.py`：

```python
from django.http import JsonResponse

from .models import UserSession
from .utils import record_user_session


class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            session_key = request.session.session_key
            current = (
                UserSession.objects
                .filter(user=user, is_current=True)
                .order_by("-created_at")
                .first()
            )
            if current is None:
                # 上线前已存在的会话：自愈式补登为当前会话
                if session_key:
                    record_user_session(request, user, session_key)
            elif current.session_key != session_key:
                # 本账号当前会话不是我这条 → 已被新设备接管
                request.session.flush()
                return JsonResponse(
                    {
                        "detail": "您的账号在其他设备登录，您已被迫下线。",
                        "reason": "session_superseded",
                        "takeover": {
                            "device_name": current.device_name,
                            "device_type": current.device_type,
                            "ip": current.ip_address,
                            "time": current.created_at.isoformat(),
                        },
                    },
                    status=401,
                )
        return self.get_response(request)
```

- [ ] **Step 4: 注册中间件**

在 `config/settings.py` 的 `MIDDLEWARE` 列表**末尾**追加一行（必须在 `AuthenticationMiddleware` 之后）：

```python
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.SingleSessionMiddleware',
]
```

- [ ] **Step 5: 运行测试确认通过**

运行：`uv run python manage.py test accounts.tests.SingleSessionMiddlewareTest`
预期：OK（5 个测试通过）。

- [ ] **Step 6: 全量回归**

运行：`uv run python manage.py test accounts`
预期：OK（所有测试通过；既有 `test_me_unauthenticated`/`test_logout_unauthenticated` 仍为 302）。

- [ ] **Step 7: 提交**

```bash
git add accounts/middleware.py config/settings.py accounts/tests.py
git commit -m "feat(accounts): SingleSessionMiddleware 实现跨设备挤下线" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: 前端请求拦截（`shared.ts`）

**Files:**
- Modify: `frontend/src/api/shared.ts`

> 前端无测试运行器；本任务以 `npm run build` 编译通过为校验门，真实行为在 Task 8 手动验证。

- [ ] **Step 1: 改写 `createRequest` 并新增 handler 注册**

将 `frontend/src/api/shared.ts` 整体替换为：

```ts
// 各 api 模块共用的请求工具。
//
// CSRF 头、FormData 自动识别、204 空响应处理、统一的错误信息提取。
// 另外拦截 401 + reason=session_superseded（其他设备登录挤下线），
// 触发由 SessionGuard 注册的回调以弹出提示。

export interface SupersedeTakeover {
  device_name?: string;
  device_type?: string;
  ip?: string | null;
  time?: string;
}

type SupersedeHandler = (takeover: SupersedeTakeover) => void;

let supersedeHandler: SupersedeHandler | null = null;

export function setSupersedeHandler(fn: SupersedeHandler | null) {
  supersedeHandler = fn;
}

export function getCSRFToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function createRequest(base: string) {
  return async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
    const isFormData = options.body instanceof FormData;
    const res = await fetch(`${base}${path}`, {
      ...options,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        "X-CSRFToken": getCSRFToken(),
        ...options.headers,
      },
      credentials: "include",
    });
    if (res.status === 204) return null as T;
    const data = await res.json();
    if (res.status === 401 && data?.reason === "session_superseded") {
      // 被新设备挤下线：触发回调弹窗（幂等由 SessionGuard 保证），随后照常抛错
      supersedeHandler?.(data.takeover ?? {});
    }
    if (!res.ok) {
      const err = new Error(data.detail || data.error || "请求失败") as Error & { status: number };
      err.status = res.status;
      throw err;
    }
    return data as T;
  };
}
```

- [ ] **Step 2: 编译校验**

运行：`npm --prefix frontend run build`
预期：构建成功，无 TS/导入错误。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/shared.ts
git commit -m "feat(frontend): 拦截 session_superseded 401 触发挤下线回调" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 被挤下线弹窗组件

**Files:**
- Create: `frontend/src/components/SessionSupersedeModal.tsx`

- [ ] **Step 1: 新建组件**

创建 `frontend/src/components/SessionSupersedeModal.tsx`：

```tsx
import { SupersedeTakeover } from "../api/shared";

export default function SessionSupersedeModal({
  takeover,
  onConfirm,
}: {
  takeover: SupersedeTakeover | null;
  onConfirm: () => void;
}) {
  if (!takeover) return null;

  const when = takeover.time ? new Date(takeover.time).toLocaleString("zh-CN") : "";
  const where = [takeover.device_name, takeover.ip ? `IP ${takeover.ip}` : ""]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 8,
          padding: 24,
          width: 380,
          maxWidth: "90vw",
          textAlign: "center",
          boxShadow: "0 8px 30px rgba(0,0,0,0.2)",
        }}
      >
        <h3 style={{ margin: "0 0 12px", fontSize: 18 }}>账号在其他设备登录</h3>
        <p style={{ color: "#374151", lineHeight: 1.6, margin: "0 0 8px" }}>
          您的账号{when ? `于 ${when} ` : ""}
          {where ? `在 ${where} ` : ""}登录，您已被迫下线。
        </p>
        <p style={{ color: "#6b7280", fontSize: 13, margin: "0 0 16px" }}>
          如非本人操作，请及时修改密码。
        </p>
        <button
          onClick={onConfirm}
          style={{
            padding: "8px 20px",
            background: "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          重新登录
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 编译校验**

运行：`npm --prefix frontend run build`
预期：构建成功。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/SessionSupersedeModal.tsx
git commit -m "feat(frontend): 被挤下线阻塞式弹窗组件" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `SessionGuard`（轮询 + 挂载）

**Files:**
- Create: `frontend/src/components/SessionGuard.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 新建 `SessionGuard`**

创建 `frontend/src/components/SessionGuard.tsx`：

```tsx
import { useEffect, useRef, useState, ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { setSupersedeHandler, SupersedeTakeover } from "../api/shared";
import { api } from "../api/client";
import SessionSupersedeModal from "./SessionSupersedeModal";

const POLL_INTERVAL_MS = 60000;

export default function SessionGuard({ children }: { children: ReactNode }) {
  const [takeover, setTakeover] = useState<SupersedeTakeover | null>(null);
  const navigate = useNavigate();
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    setSupersedeHandler((t) => {
      setTakeover((prev) => prev ?? t); // 幂等：已弹窗则不覆盖
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current); // 已被挤，停止轮询
        intervalRef.current = null;
      }
    });

    intervalRef.current = window.setInterval(() => {
      api.me().catch(() => {}); // 被挤时由 shared.ts 拦截器弹窗；其它错误吞掉
    }, POLL_INTERVAL_MS);

    return () => {
      setSupersedeHandler(null);
      if (intervalRef.current !== null) window.clearInterval(intervalRef.current);
    };
  }, []);

  function handleConfirm() {
    setTakeover(null);
    navigate("/login", { replace: true });
  }

  return (
    <>
      {children}
      <SessionSupersedeModal takeover={takeover} onConfirm={handleConfirm} />
    </>
  );
}
```

- [ ] **Step 2: 在 `App.tsx` 挂载（两处精确改动）**

`frontend/src/App.tsx` 当前结构：第 3 行是 `import ProtectedRoute ...`，`App()` 内为 `<HashRouter>` 直接包 `<Suspense>`。只做下面两处精确替换，**其余内容（含所有 `import` 与 `<Routes>` 内的全部路由）一律不动**。

改动 A —— 新增 import。把第 3 行：

```tsx
import ProtectedRoute from "./components/ProtectedRoute";
```
替换为：

```tsx
import ProtectedRoute from "./components/ProtectedRoute";
import SessionGuard from "./components/SessionGuard";
```

改动 B（开标签）—— 把这段：

```tsx
    <HashRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
```
替换为（仅多了一行 `<SessionGuard>`）：

```tsx
    <HashRouter>
      <SessionGuard>
      <Suspense fallback={<Loading />}>
        <Routes>
```

改动 B（闭标签）—— 把这段：

```tsx
        </Routes>
      </Suspense>
    </HashRouter>
```
替换为（仅多了一行 `</SessionGuard>`）：

```tsx
        </Routes>
      </Suspense>
      </SessionGuard>
    </HashRouter>
```

`<Routes>` 及其全部路由项保持原样不动。改完后 `SessionGuard` 位于 `<HashRouter>` 内，`useNavigate` 可用。

- [ ] **Step 3: 编译校验**

运行：`npm --prefix frontend run build`
预期：构建成功。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/SessionGuard.tsx frontend/src/App.tsx
git commit -m "feat(frontend): SessionGuard 轮询检测与挤下线弹窗挂载" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: 手动端到端验证

> 无代码改动，不提交。需要两个独立浏览器（或普通窗口 + 隐身窗口）。

- [ ] **Step 1: 启动服务**

```bash
uv run python manage.py runserver     # 后端
# 另一个终端：
npm --prefix frontend run dev          # 前端 http://localhost:3000
```

- [ ] **Step 2: 双设备挤号主流程**

1. 浏览器 A 登录账号 `u`，进入 `/tasks` 等受保护页。
2. 浏览器 B（隐身窗口）用同一账号 `u` 登录，确认 B 能正常进入。
3. 回到浏览器 A：
   - A 触发任意请求（如刷新或切换页面）→ 应**立即弹出**"账号在其他设备登录"模态框，显示 B 的设备类型/OS/IP/时间。
   - 或 A 保持不动等待 ≤60s → 由轮询触发同样弹窗。
4. 点"重新登录" → 跳转到 `/login`。
5. 浏览器 A 重新登录后，浏览器 B 应被同样挤下线弹窗。

- [ ] **Step 3: 边界验证**

- 同一浏览器重复登录：不自我弹窗、正常使用。
- 未登录访问 `/auth/me/`：返回 302 跳登录页（非弹窗、非 500）。
- 登出后再登录：正常。
- 非挤号场景下 60s 轮询不产生可见副作用。

- [ ] **Step 4: 全量回归测试**

```bash
uv run python manage.py test accounts
npm --prefix frontend run build
```
预期：后端测试全绿；前端构建成功。

---

## 完成标准

- 后端：`accounts` 全部测试通过；同一账号多设备登录，旧设备下次请求得到 `401 {reason:"session_superseded", takeover:{...}}`。
- 前端：构建通过；旧设备被挤时弹出阻塞式弹窗显示新设备信息，点"重新登录"跳 `/login`。
- 既有功能（登录、登出、`/auth/me/`、权限校验）不受影响。
