# 登录安全增强：轮询提速 / 登录后自检 / 登录记录 / 10 分钟保护 设计

- 日期：2026-07-21
- 状态：已确认，待实现
- 适用范围：全用户（含管理员），不豁免
- 前置：建立在 `2026-07-11-single-session-kickout-design.md` 的单会话挤号能力之上，不改其判定逻辑

## 1. 背景与目标

现有"单会话挤号"系统存在四处不足，本次一并补齐：

1. **感知慢**：被挤设备靠 `SessionGuard` 每 60s 轮询 `/auth/me/` 才发现，最坏 60s 延迟。
2. **假登录态**：登录接口返回 200 但会话实际已失效（被并发登录挤掉等）时，前端会进入"看起来已登录、实际未登录"的假态。
3. **无可查记录**：`record_user_session` 每次登录都删除旧会话，用户无法回看自己的登录历史。
4. **可被瞬时挤号**：拿到账号密码的人可在合法用户登录后立刻登录把其挤下线，缺少缓冲。

### 1.1 已确认的产品决策

| 决策点 | 选择 |
|---|---|
| "异地登录"判定依据 | 维持现有"新设备挤号"判定，**不做** IP 地理定位、不做常用地区比对 |
| 灵敏度手段 | 轮询间隔 60s → **5s**（不引入 WebSocket/SSE） |
| 登录时反应 | 登录成功后立即一次 `api.me()` 自检，防假登录态 |
| 登录记录 | 复用 `UserSession` 表保留历史（每用户最近 20 条），个人中心可查 |
| 10 分钟保护 | 登录后 10 分钟内，**拒绝**他人在新会话登录该账号；满 10 分钟或原会话主动登出后恢复挤号 |
| 保护期他方登录行为 | **拒绝**（返回 409 提示），保持单会话不变；换设备需先主动登出 |
| 同浏览器再认证 | 不拦截（同一 `session_key` 视为同一会话，避免误伤刷新/重提交） |
| 错误密码 | 不触发保护判定、不泄露保护状态（先认证后判保护） |

## 2. 方案对比

仅"登录记录"与"保护期行为"有架构选择，已在确认环节定案，此处留档：

| 维度 | 方案 | 结论 |
|---|---|---|
| 登录记录存储 | A. 复用 `UserSession`（停删 + 裁剪到 20 条）/ B. 新建 `LoginEvent` 审计表 / C. 复用但不裁剪 | ✅ A（零迁移、字段已齐；B 过度；C 无界增长） |
| 保护期他方登录 | A. 拒绝 B 登录 / B. 允许 B 但 10 分钟内不挤 A（双会话并存） | ✅ A（保单会话、安全、与"除非主动登出"一致） |
| 灵敏度 | A. 轮询提速到 5s / B. SSE/WebSocket 推送 | ✅ A（用户指定；零新依赖） |

## 3. 架构概览

```
[设备 B 登录 POST /auth/login/]
   │ authenticate 通过
   ▼
login_view 保护判定
   │ 查 user 的 is_current=True 旧会话
   │ ├ 无 / 已登出                 → 放行
   │ ├ age ≥ 600s                  → 放行（正常挤号）
   │ ├ age < 600s 且 session_key 同 → 放行（同会话再认证）
   │ └ age < 600s 且 session_key 异 → 拒绝 409 {reason:"login_protection", retry_after}
   ▼（放行）
login() → user_logged_in 信号 → record_user_session
   │ ① 该用户其它行 is_current=False
   │ ② upsert 本 session_key(is_current=True, 设备信息)
   │ ③ 保留历史，裁剪到最近 20 条（不再全删）
   ▼
[设备 B 前端] 登录后立即 api.me() 自检
   │ 200 → onLoggedIn + 跳转；401 → 不跳首页，supersede 弹窗由 SessionGuard 弹出（防假登录）

[设备 A 被挤] 每 5s 轮询 api.me()
   ▼ SingleSessionMiddleware：current.session_key != 我 → 401 session_superseded → 弹窗

[个人中心] GET /auth/sessions/ → 展示最近 20 条登录记录（设备/IP/时间，当前会话高亮）
```

## 4. 数据模型

**无变更、无迁移。** `accounts.UserSession` 已具备所需字段：`user / session_key / ip_address / user_agent / device_type / device_name / created_at / is_current`。本次仅改读写行为（保留历史 + 裁剪）与登录门禁逻辑。

## 5. 后端实现

### 5.1 登录历史保留 `accounts/utils.py`

`record_user_session` 末尾把"删除所有非 current 行"改为"裁剪到每用户最近 `SESSION_HISTORY_LIMIT` 条"：

```python
SESSION_HISTORY_LIMIT = 20  # 每用户保留的登录记录条数

# 旧：UserSession.objects.filter(user=user, is_current=False).delete()
# 新：保留最近 N 条（含当前），删除更早的
keep_ids = list(
    UserSession.objects.filter(user=user)
    .order_by("-created_at", "-id")[:SESSION_HISTORY_LIMIT]
    .values_list("id", flat=True)
)
UserSession.objects.filter(user=user).exclude(id__in=keep_ids).delete()
```

- 当前会话 `created_at=now` 必在最近 N 条内，始终保留。
- `update(is_current=False)` + upsert 逻辑不变，挤号判定（按 `is_current=True`）不受影响。

### 5.2 10 分钟登录保护 `accounts/views.py`

新增模块常量 `LOGIN_PROTECTION_SECONDS = 600`。在 `login_view` 中，`authenticate` 通过、`login(request, user)` **之前**插入门禁：

```python
from datetime import timedelta
from django.utils import timezone
from .models import UserSession

LOGIN_PROTECTION_SECONDS = 600

# ...在 user is not None 之后、login() 之前：
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
```

- **顺序**：先 `authenticate` 再判保护。错误密码直接 401 `Invalid credentials`，不触达保护逻辑、不泄露"该账号是否在保护期"。
- **同会话豁免**：`existing.session_key == request.session.session_key` 时放行（同一浏览器已登录后再次提交登录，不自我拦截）。已登录浏览器必带会话 cookie，`session_key` 可读。
- **登出即解保护**：依赖 §5.4——`logout_view` 登出时把当前行置 `is_current=False`，下次登录 `existing is None` → 放行。

### 5.3 登录记录接口 `accounts/views.py` + `accounts/urls.py`

```python
from django.views.decorators.http import require_GET

@require_GET
@login_required
def sessions_view(request):
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

`accounts/urls.py` 新增：`path("sessions/", views.sessions_view, name="sessions")`。

### 5.4 登出清理 `accounts/views.py::logout_view`

现状：`logout_view` 仅 `auth_logout(request)`（会 `flush()` 会话），**不**动 `UserSession`，导致登出后 `is_current=True` 行残留 → 保护门禁误判、登出后无法在 10 分钟内重新登录。必做改造：

```python
from .models import UserSession

@require_POST
@login_required
def logout_view(request):
    user = request.user                 # 先取用户：auth_logout 后 request.user 变匿名
    auth_logout(request)
    UserSession.objects.filter(user=user, is_current=True).update(is_current=False)
    return JsonResponse({"message": "Logged out"})
```

- 置 `is_current=False`（而非删除）：该次登录仍作为历史保留在"登录记录"中，只是不再是当前会话。
- 必须在 `auth_logout` 之前捕获 `request.user`，否则刷新会话后取到匿名用户。

## 6. 前端实现

### 6.1 错误对象增强 `frontend/src/api/shared.ts`

`if (!res.ok)` 分支构造 Error 时补挂 `reason` / `retry_after`，供前端分支：

```ts
const err = new Error(data.detail || data.error || "请求失败") as Error & {
  status: number; reason?: string; retry_after?: number;
};
err.status = res.status;
err.reason = data?.reason;
if (typeof data?.retry_after === "number") err.retry_after = data.retry_after;
throw err;
```

### 6.2 轮询提速 `frontend/src/components/SessionGuard.tsx`

`POLL_INTERVAL_MS = 60000` → `5000`。注释说明：内部工具并发低，5s 心跳可接受；被挤设备最迟 ~5s 感知（原 60s）。其余（拦截器回调、弹窗后停轮询）不变。

### 6.3 登录后自检 + 保护期提示 `frontend/src/components/LoginModal.tsx`

`handleSubmit` 改为：登录成功 → 内嵌一次 `api.me()` 自检 → 通过则跳转。

```tsx
try {
  if (method === "username") await api.login(account.trim(), password);
  else await api.loginWithEmail(account.trim(), password);

  // 防假登录：立即自检；若刚建的会话已被挤/未真正建立，不进入"已登录"假态
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
```

- 自检 401 视为"刚登录即被挤"→ 关登录框，由 SessionGuard 弹 supersede 模态；**不**跳首页。
- `login_protection` 优先于通用映射；其余沿用既有 `LOGIN_ERROR_ZH` 中文映射。

### 6.4 登录记录卡片 `frontend/src/pages/ProfilePage.tsx`

- `api/client.ts` 新增 `listSessions: () => request("/sessions/")`。
- ProfilePage 挂载时拉取 `api.listSessions()`，新增"登录记录"卡片：按时间倒序列 `device_name · 设备类型 · IP · 时间`，`is_current` 行高亮（如"当前本机"标记）。沿用 cobalt 卡片风格（`.cs` 作用域约定，与现有卡片一致）。

## 7. 受影响文件清单

**后端**
- `accounts/utils.py`（`record_user_session` 改为保留 + 裁剪；新增 `SESSION_HISTORY_LIMIT`）
- `accounts/views.py`（`login_view` 加保护门禁；新增 `sessions_view`；`logout_view` 清理当前会话；新增 `LOGIN_PROTECTION_SECONDS`）
- `accounts/urls.py`（+ `sessions/`）
- `accounts/tests.py`（更新受影响断言 + 新增用例）
- **无迁移**

**前端**
- `frontend/src/api/shared.ts`（Error 补挂 `reason` / `retry_after`）
- `frontend/src/api/client.ts`（+ `listSessions`）
- `frontend/src/components/SessionGuard.tsx`（轮询 60s → 5s）
- `frontend/src/components/LoginModal.tsx`（登录后自检 + 保护期提示）
- `frontend/src/pages/ProfilePage.tsx`（登录记录卡片）

## 8. 流程与边界情况

- **保护期内他人登录**：409 `login_protection`，旧会话保持 `is_current=True` 且可继续使用。
- **满 10 分钟**：第二次登录放行，正常挤号；旧设备 ≤5s 内被轮询感知弹窗。
- **主动登出**：`logout_view` 经 §5.4 改造后，登出会把当前行置 `is_current=False`；下次登录无 `is_current=True` 行 → 放行（解保护）。
- **同浏览器再认证**：`session_key` 相同 → 放行，不自我拦截。
- **错误密码**：401 `Invalid credentials`，不触达保护逻辑。
- **登录记录裁剪**：每次登录后该用户仅保留最近 20 条；当前会话始终在内。
- **保护期与轮询/记录互不影响**：轮询 `me()` 非登录，不触保护；记录接口只读。

## 9. 性能

- 轮询 60s → 5s：每个已登录标签页 `/auth/me/` 频率 ×12。内部工具并发低，可接受；后续若用户量上升可改回更长间隔或加指数退避（YAGNI，暂不做）。
- `record_user_session` 裁剪：每次登录 +1 次列表查询 +1 次按 id 删除，量级固定（每用户 ≤20 行），可忽略。
- 保护判定：登录路径 +1 次 `(user, is_current)` 索引查询。

## 10. 测试

### 10.1 后端 `accounts/tests.py`

**需更新的现有用例**（行为变更：保留历史 + 保护门禁）：
- 任何"同账号连续两次登录"用例（如 `test_second_login_supersedes_first`、`test_second_device_login_leaves_single_current_row`）：第二次登录现会被保护拒绝。改为先把首次会话 `created_at` 置为 >10 分钟前（`UserSession.objects.update(created_at=...)`）再登第二次，以验证挤号路径。
- 断言"二次登录后仅剩 1 条"的用例：改为断言"`is_current=True` 唯一、总条数 ≥2（历史保留）"。

**新增用例**：
- 历史裁剪：同用户登录 >20 次 → `UserSession` 该用户行数 ≤20，且当前会话在内。
- `/auth/sessions/`：仅返回本人、按 `-created_at` 倒序、≤20 条、含 `is_current` 字段；未登录访问 401/重定向。
- 保护期：
  - 首次登录成功 → 10 分钟内第二次（不同会话）登录 → 409、`reason=="login_protection"`、`retry_after>0`、首次会话仍 `is_current=True`。
  - 把首次会话 `created_at` 老化到 >10 分钟 → 第二次登录 200、发生挤号。
  - 首次登录后 `logout` → 第二次登录 200（验证登出解保护，依赖 §8 的 logout 清理）。
  - 同一 `session_key` 再次登录（同会话再认证）→ 200，不被保护拦截。
  - 错误密码 → 401 `Invalid credentials`，不返回 `login_protection`。

### 10.2 前端（手动 + 构建）

- `npx tsc --noEmit` 与 `npm run build` 通过。
- 双浏览器同账号：保护期内 B 登录被拒、提示文案与倒计时正确；满 10 分钟 B 登录成功，A ≤5s 弹挤号窗。
- 登录后立即自检：构造并发挤号（A 登录后立刻另一处再登把 A 挤掉）→ A 不进入假登录态，直接弹 supersede 窗。
- 个人中心"登录记录"卡片：展示最近登录、当前会话高亮。

## 11. 不做（YAGNI）

- IP 地理定位 / 常用地区比对（维持现有挤号判定）。
- WebSocket / SSE 实时推送（用 5s 轮询）。
- 登录记录分页 / 筛选 / 远程踢下线（仅最近 20 条只读展示）。
- 保护期时长、保留条数的 settings 化（模块常量即可）。
- 管理员/社长豁免。
