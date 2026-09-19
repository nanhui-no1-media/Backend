# 身份验证

> 相关：[账号 API](../api/accounts.md) · [访问控制](access-control.md) · [ADR-0006](../adr/0006-verification-model.md) · [ADR-0013](../adr/0013-appointment-verification-channel.md)

## 为什么要验证

注册与验证**分离**：任何人都可注册（用户名 + 密码 + Turnstile 人机验证，邮箱可选），但新账号默认是**访客**，功能受限；通过任一验证通道后才成为正式「用户」。

- 验证是**身份态**，不是权限：它不授予任何具体能力（能力仍由组 → 权限分配，见 [访问控制](access-control.md)）；它只把账号从「访客」提升为「用户」，放开各模块中标注「已验证」的端点（如任务认领、活动参与）。
- **未验证也可以登录**——验证不卡登录，只卡「参与 / 写操作」。

## 核心模型：任一通道通过即「已验证」

```
账号「已验证」 ⇔ 至少一条验证通道 approved
```

- `Verification(user, channel, status)`：每 `(用户, 通道)` 一行，状态 `pending / approved / rejected`，就地更新；存在 `approved` 行即 `is_verified = true`。
- 人工通道的证据（`IdentityProof`）**永久留底**，审核通过或重新提交都不删除。
- 人工通道驳回后**允许重交**：通道行回到 `pending`，新证明累加。

### 三条通道

| 通道 | 触发方式 | 说明 |
|---|---|---|
| `manual` 人工审批 | 用户提交身份证明 → 信息组审核 | 主通道：真实姓名 + 证明件上传 |
| `email` 邮箱 | 用户自助绑定 → 点邮件链接确认 | 验证通过才把地址晋升为账号邮箱 |
| `appointment` 后台委任 | 账号被授予 `is_staff` / `is_superuser` 时**自动** approved | 只读、无自助申请；撤销委任则删行、退回未验证 |

> 管理员 / 超级管理员不走自助流程——委任本身就是一条验证通道（[ADR-0013](../adr/0013-appointment-verification-channel.md)）。注意验证轴与权限轴的「逃生舱」相互独立：超管的 `has_perm` 恒真（[ADR-0005](../adr/0005-access-control-principle.md)），而验证面板照常显示其「后台委任」通道状态。

## 用户视角

1. **注册** → 默认访客（无验证记录）。
2. 打开个人中心的**验证面板**（`GET /auth/verification/`）：数据驱动的通道状态卡，查状态、绑邮箱、提交证明都在这里。
3. **走邮箱通道**：`POST /auth/verification/email/bind/` 绑定地址 → 收到验证邮件 → 点链接确认（`/auth/verify-email/`）→ 通道 approved，地址晋升为账号邮箱。
4. **走人工通道**：`POST /auth/verification/manual/submit/` 提交真实姓名 + 证明件 → 等待审核。
5. **结果**：通过 → 徽章变「用户」，受限功能放开；驳回 → 邮件通知，可重新提交。

> 没收到邮件可用 `/auth/resend-verification/` 重发；邮箱登录**只认已验证邮箱**，待验地址登不进。

## 管理员视角

- **审核队列**：`/auth/identity-reviews/`（列表 / 详情 + 三个动作：**通过 / 驳回 / 停用账号**），需权限 `accounts.can_review_identity`。
- **停用账号**是账号级处置：`is_active = False` + 吊销会话，与通道状态无关。
- 通过与驳回会发送邮件通知；所有动作在 Django Admin 中亦可操作。
- 审核用的证明文件经带鉴权的视图读取（`/auth/identity-proof/<id>/`），**不经**公开媒体路径。

## 边界与细节

- **密码重置**发往已验证邮箱；没有绑定邮箱 → 走信息组人工。
- **会话相关**（单会话挤号、登录保护）属于会话层，与验证体系无关，详见 [API 总览](../api/README.md#错误格式)。
- 验证面板**仅本人可见**。
- 加新通道 = 加 `CHANNEL` 枚举 + 实现该通道流程，`is_verified` 判定自动纳入（[ADR-0006](../adr/0006-verification-model.md)）。
