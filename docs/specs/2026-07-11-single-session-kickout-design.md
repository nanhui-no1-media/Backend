# 单会话强制下线（跨设备登录挤号）设计

- 日期：2026-07-11
- 状态：已确认，待实现
- 适用范围：全用户（含管理员），不豁免

## 1. 背景与目标

当前系统基于 Django 会话（cookie + DB，`SessionAuthentication`），默认允许同一账号在多个设备同时保持登录。产品需要一个"挤号"能力：**当账号在一个新设备登录时，原设备被强制下线，并弹出说明（含新登录设备的 IP / 设备 / 时间）。** 即一个账号同一时间只允许一个会话生效。

典型场景（QQ/微信式异地登录提示）：用户在 A 设备登录后，又在 B 设备登录 → A 设备弹出"您的账号在其他设备登录，您已被迫下线" → 用户点"重新登录"回到登录页。

### 1.1 已确认的产品决策

| 决策点 | 选择 |
|---|---|
| 行为 | 强制下线 + 弹窗提示，弹窗展示新登录设备信息 |
| 单会话边界 | 一个账号同时只有一个会话生效；后登录者接管 |
| 提示时机 | 尽量即时：下一次接口请求即弹窗 + 60s 轻量轮询覆盖空闲 |
| 通知机制 | 中间件检测 + 401 携带设备信息（方案 A），不引入 WebSocket |
| 管理员/社长豁免 | 不豁免，全员生效 |
| 弹窗是否显示 IP | 显示 |
| 被挤后跳转 | 不自动跳转；只弹阻塞式模态框，用户点"重新登录"才跳 `/login`（避免打断正在填的表单丢数据） |

## 2. 方案对比（机制）

| 方案 | 原理 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| **A. 中间件 + 60s 轮询** | 中间件在每个已登录请求检查"我的会话是否仍是该账号最新的"；否则返回带设备信息的 401。前端在 `createRequest` 收口拦截该 401 弹窗；前端再加 60s 轮询 `/auth/me/` 覆盖空闲 | 零新依赖；下次操作即弹窗（近乎即时）；设备信息随 401 下发，无需额外接口；逻辑集中好测 | 每个已登录请求多 1 次 DB 查询（小项目可忽略） | ✅ 采用 |
| B. 纯轮询 | 只靠前端定时轮询状态接口 | 后端最简 | 有轮询延迟；点击操作不会立即触发 | ✗ |
| C. WebSocket（Django Channels） | 服务端实时推送"被挤"事件 | 真·0 延迟 | 需引入 Channels + Redis、ASGI 改造、断线重连，复杂度与部署成本显著上升 | ✗ 过度 |

## 3. 架构概览

```
[设备 B 登录]
   │ user_logged_in 信号
   ▼
accounts/signals.py::record_user_session
   │ 1) 把该用户其它 UserSession.is_current 置 False
   │ 2) 新建/更新本 session_key 的 UserSession(is_current=True, 设备信息)
   │ 3) 删除该用户非 current 的旧记录
   ▼
[设备 A 后续请求（或 60s 轮询 /auth/me/）]
   │
   ▼
accounts/middleware.py::SingleSessionMiddleware
   │ current = 该用户 is_current=True 的行
   │ current.session_key != 我的 session_key  →  我已被接管
   ▼
返回 401 {reason:"session_superseded", takeover:{device_name, device_type, ip, time}}
   │
   ▼
frontend shared.ts::createRequest  拦截 401+reason
   │ 调用 setSupersedeHandler 注册的回调(takeover)
   ▼
SessionGuard 显示阻塞式 SessionSupersedeModal
   │ 用户点"重新登录" → navigate("/login")
```

## 4. 数据模型

新增 `accounts.UserSession`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `user` | FK(User, on_delete=CASCADE, related_name="login_sessions") | 所属账号 |
| `session_key` | CharField(max_length=40, db_index=True) | 对应 `django_session.session_key` |
| `ip_address` | GenericIPAddressField(null=True, blank=True) | 登录 IP |
| `user_agent` | TextField(blank=True, default="") | 原始 UA |
| `device_type` | CharField(max_length=16, default="Unknown") | Desktop / Mobile / Tablet / Bot |
| `device_name` | CharField(max_length=128, blank=True, default="") | 如 "Chrome · macOS 10.15" |
| `created_at` | DateTimeField(auto_now_add=True) | 登录时间 |
| `is_current` | BooleanField(default=True) | 每个用户仅一条为 True |

- `Meta.indexes = [Index(["user", "is_current"])]`，`ordering = ["-created_at"]`。
- 不引入 UA 解析依赖：`device_type` / `device_name` 由轻量正则解析得出。
- 不做 IP 地理定位（YAGNI；需 GeoIP 库与数据库）。
- 不设 `last_activity_at`（无消费方，YAGNI），表增长由"登录时清理"控制。

配套生成迁移：`uv run python manage.py makemigrations accounts`。

## 5. 后端实现

### 5.1 工具函数 `accounts/utils.py`（新建）

- `get_client_ip(request) -> str | None`：默认取 `REMOTE_ADDR`；预留 `X-Forwarded-For` 读取（受 settings 开关控制，防伪造），当前阶段仅 `REMOTE_ADDR`。
- `parse_user_agent(ua) -> tuple[str, str]`：返回 `(device_type, device_name)`，用正则识别 `Mobile / Tablet / Bot` 否则 `Desktop`，并拼出"浏览器 · 操作系统"短串。
- `record_user_session(request, user, session_key) -> UserSession`：原子事务内 ① 把该用户所有行 `is_current=False`；② `update_or_create(session_key=...)` 写入设备信息并 `is_current=True`；③ 删除该用户非 current 行。**供信号与中间件"补登"分支共用，避免重复。**

### 5.2 登录信号 `accounts/signals.py`（新建）

```python
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .utils import record_user_session

@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    key = request.session.session_key
    if key:
        record_user_session(request, user, key)
```

- 在 `accounts/apps.py` 的 `AccountsConfig.ready()` 中 `from . import signals` 连接。
- 信号在 `login()` 内部、`request.session.cycle_key()` 之后触发，此时 `session_key` 已就绪，读取安全。
- 覆盖所有登录入口（含 `/admin/` 与未来新增登录方式）。

### 5.3 强制下线中间件 `accounts/middleware.py`（新建）

```python
class SingleSessionMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            sk = request.session.session_key
            current = (UserSession.objects
                       .filter(user=user, is_current=True)
                       .order_by("-created_at").first())
            if current is None:
                # 上线前已存在的会话：自愈式补登为当前会话
                if sk: record_user_session(request, user, sk)
            elif current.session_key != sk:
                # 我已被接管 → 作废旧会话并返回带设备信息的 401
                request.session.flush()
                return JsonResponse({
                    "detail": "您的账号在其他设备登录，您已被迫下线。",
                    "reason": "session_superseded",
                    "takeover": {
                        "device_name": current.device_name,
                        "device_type": current.device_type,
                        "ip": current.ip_address,
                        "time": current.created_at.isoformat(),
                    },
                }, status=401)
        return self.get_response(request)
```

- 在 `config/settings.py` 的 `MIDDLEWARE` **末尾**注册（必须在 `AuthenticationMiddleware` 之后，`request.user` 才已就绪）。
- **鲁棒性**：不论我的行是否已被清理，只要"本账号当前会话不是我这条" → 判定被接管并踢出；若本账号无任何记录 → 自愈补登（平滑上线）。每已登录请求 1 次查询。
- `request.session.flush()` 由随后的 `SessionMiddleware` 处理响应时落地；旧 cookie 指向的会话不复存在。
- 普通 401（未登录 / 会话自然过期）不受影响，本中间件只对 `is_authenticated` 生效。

## 6. 前端实现

### 6.1 拦截器 `frontend/src/api/shared.ts`

在 `createRequest` 现有 `if (!res.ok)` 分支**之前**插入：

```ts
if (res.status === 401) {
  if (data?.reason === "session_superseded") {
    supersedeHandler?.(data.takeover);   // 注册回调；幂等，内部防重入
  }
}
```

并导出 `setSupersedeHandler(fn)` 用于注册回调。其余逻辑不变；其它 401 保持原行为（不越界）。

### 6.2 `SessionGuard`（新建 `frontend/src/components/SessionGuard.tsx`）

挂在 `App.tsx` 的 `<HashRouter>` 内、`<Routes>` 外：

- 挂载时 `setSupersedeHandler(showModal)`；
- 状态 `{ open: boolean, takeover?: {...} }`；收到回调且 `!open` 时 `setOpen(true)`；
- **轮询**：认证期间每 **60s** 调一次 `api.me()`，`.catch(() => {})` 吞错（被挤时由 6.1 拦截器接管弹窗）；弹窗显示后 `clearInterval` 停止，防重复弹；
- 渲染 `<SessionSupersedeModal>`（条件 `open`）。

### 6.3 `SessionSupersedeModal`（新建 `frontend/src/components/SessionSupersedeModal.tsx`）

- **阻塞式**：置顶层（`position: fixed`，高 z-index，遮罩），**无关闭叉**，唯一按钮"重新登录"。
- 文案：`您的账号于 {time} 在 {device_name}（IP {ip}）登录，您已被迫下线。如非本人操作，请及时修改密码。`
- `time` 用 `new Date(iso).toLocaleString("zh-CN")` 本地化展示。
- 点"重新登录" → 清状态 → `navigate("/login", { replace: true })`。

### 6.4 `App.tsx`

在 `<HashRouter>` 内包一层 `<SessionGuard>`，使其能用路由 `navigate`。

## 7. 受影响文件清单

**后端**
- `accounts/models.py`（+`UserSession`）
- 新迁移（`makemigrations accounts`）
- `accounts/utils.py`（新：`get_client_ip` / `parse_user_agent` / `record_user_session`）
- `accounts/signals.py`（新：`on_user_logged_in`）
- `accounts/apps.py`（`ready()` 连接信号）
- `accounts/middleware.py`（新：`SingleSessionMiddleware`）
- `config/settings.py`（`MIDDLEWARE` 末尾加一行）

**前端**
- `frontend/src/api/shared.ts`（401 拦截 + `setSupersedeHandler`）
- `frontend/src/components/SessionGuard.tsx`（新）
- `frontend/src/components/SessionSupersedeModal.tsx`（新）
- `frontend/src/App.tsx`（挂载 `SessionGuard`）

## 8. 流程与边界情况

- **正常登录**：信号写入 `UserSession(is_current=True)`，中间件放行。
- **同浏览器重复登录**：`session_key` 相同 → `update_or_create` 仅更新、不自我踢。
- **新设备挤号**：旧设备下一次请求（或 ≤60s 轮询）→ 401 弹窗 → 点按钮跳登录。
- **近乎同时两处登录**：`is_current` 最后写入者生效，另一方下次请求被踢（可接受）。
- **上线前的存量会话**：中间件 `current is None` 分支自愈补登，平滑上线，不打断在线用户。
- **清理**：每次登录删除该用户非 current 行，表保持小；被挤设备的 401 不依赖旧行存在（中间件按"当前会话非我"判定）。
- **管理后台**：信号对 `/admin/` 同样生效，管理员也受单会话约束（按已确认决策不豁免）。
- **隐私**：记录 IP/UA；校园内部系统可接受。

## 9. 性能

- 每个已登录请求 +1 次 DB 查询（`UserSession` 按 `(user, is_current)` 索引，很快）。小项目无影响。
- 未来可优化：`cache.set(f"user:{id}:cur_session", sk, ttl)` + 登录时失效，中间件优先读缓存（YAGNI，暂不做）。

## 10. 测试

### 10.1 后端（`accounts/tests.py`）

- A 登录 → 存在 `is_current=True` 行，含 IP/UA/`device_type`。
- 同账号 B 登录 → A 行 `is_current=False`、B 行 `is_current=True`；A 旧非 current 行被清理。
- A 再次请求 → 401、`reason == "session_superseded"`、`takeover` 含 B 的 `device_name/ip/time`。
- 同一 `session_key` 再登录 → 不产生自我踢出（A 仍可请求）。
- 中间件对匿名请求放行（不抛错）。
- 存量会话（无 `UserSession` 行）首次请求 → 自愈补登、返回 200。
- 普通 401（未登录访问受保护接口）行为不变。

### 10.2 前端（手动验证）

- 双浏览器同账号：B 登录后，A 触发任意请求 → 弹窗显示 B 的设备信息与 IP；点"重新登录"跳 `/login`。
- A 空闲不动：≤60s 后由轮询触发同样弹窗。
- 弹窗不可叉掉、不重复弹。
- 非挤号场景（正常使用、登出）不受影响。

## 11. 不做（YAGNI）

- 设备管理页（列出/远程踢掉其它设备）。
- IP 地理定位显示。
- WebSocket 实时推送。
- 管理员/社长多会话豁免开关。
- 被挤自动跳转登录（保持停原页 + 模态框，由用户确认）。
