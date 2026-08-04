# 访问控制原则（角色能力 = 权限）

日期：2026-08-03 · 与 jinha 协作

## 原则

**控制任何东西的访问时，直接定义一个权限（`Permission`），用 `has_perm` 判定——绝不检查组名或别的什么。** 权限由组分配，组决定身份，组由人类手动管理。前端据能力（`can_*`）做对应限制（禁用 / 隐藏按钮等）。

本 ADR 把这条原则细化成九条可执行决策，并钉死四个正交轴的边界。

## 背景

2026-07-19 已完成「角色 → 权限」迁移（见 `docs/specs/2026-07-19-role-to-permission-migration-design.md`）：把散落各处的 `user.groups.filter(name="社长")` / `name="信息组"` 硬编码换成 Django `Permission` + `has_perm`。本 ADR 是该迁移沉淀下来的**常驻原则**，并补齐迁移未覆盖的边界（权限词汇、前端契约、读、逃生舱、徽章等），全部经一轮 grilling 与用户逐条确认。

## 四个正交轴（模型全景）

| 轴 | 来源 | 用途 |
|---|---|---|
| **身份徽章** | 登录态 + 标志位（`is_superuser`/`is_staff`/`profile.identity_verified`） | 展示标题 + 徽章配色（访客 / 用户 / 管理员 / 超级管理员） |
| **角色能力** | `user.has_perm(...)` | **全部访问控制**（API 门禁、按钮显隐、可见性、通知路由） |
| **组成员身份** | `user.groups` | 仅作「所属组: X」纯文本展示，排在徽章之后 |
| **对象所有权** | `creator==user`、`viewer==viewed` | 每行的组合规则 |

四轴各管一摊，互不替代。能力（权限）是**唯一**的访问控制轴。

## 九条决策

1. **范围——权限是能力轴；所有权 / 身份态 / 可见性是正交轴。** 「访问控制」指「凭角色，谁**能**做 X」；「**这条**记录能不能动」是所有权（`creator==user`），不是权限。故 `tasks/permissions.py:CanModifyTask` 写 `has_perm("tasks.manage_tasks") or obj.creator==user` 是**合法**的，不算违反原则——所有权是另一轴，与权限组合。同理 `accounts/permissions.py:IsIdentityVerified`（身份审核态门禁）、`accounts/visibility.py`（按所有权的字段掩码）都是正交轴，不是漏成权限的口子。

2. **权限词汇——Django 默认 CRUD（`view`/`add`/`change`/`delete`）+ 命名工作流权限。** Django 每个 app_label 自动生成 4 个模型权限，免费用，不重复造 `create_news`。非纯记录变更的动作（审批、指派、管理）用 `Meta.permissions` 命名独立权限：`tasks.manage_tasks` / `tasks.assign_task` / `tasks.manage_tags` / `proposals.approve_proposal` / `proposals.view_feedback`。不硬塞进「读 / 写 / 修改」三件套——工作流动作（如审批）根本不是「写」。

3. **前端契约——语义化 `can_*` 能力布尔（服务端算），不喂原始权限代号。** `accounts/views.py:_capabilities(user)` 把 `has_perm` 派生为 `can_manage_news` / `can_approve_proposals` 等布尔；前端从不接触 `news.change_news` 这类代号。能力是**纯角色投影**（"凭你的角色能不能做 X"），**不是**"能不能动这条"——后者由前端拿 `is_owner` / 对象字段另行组合（如编辑按钮显隐 = `can_manage_tasks || is_creator`）。

4. **能力目录单一源——后端为唯一事实源，API 永远返回全量键（含 false）。** `/auth/me/` 的 `permissions` 字段恒列全部能力键（true / false 都在）。前端 `PermissionsPanel` 的标签表（`CAP_LABELS`）只是**展示层**（中文标签天然属前端）。**补一道契约测试**断言「后端能力键集合 == 前端预期键集合」，杜绝静默漂移（后端加键、前端漏改 → 面板漏显）。

5. **何时拆新权限——三条任一即拆，否则并入。** (a) **持有者现实中可能不同**——即便今天都归社长，也能想象某角色有其一无其二（审批者 vs 编辑者）；(b) **前端要门禁一个独立 affordance**（独立按钮 / Tab / 区块）；(c) **需要独立审计 / 问责**。**否则**用最粗的、能精确表达该能力的已有权限；Django 已给的 CRUD 权限不要重造。默认偏粗。例：`approve_proposal` 与 `change_proposal` 该拆（未来可有"只审批不改"的审核者，且前端审批按钮独立）；`create_news` 不该造（`news.add_news` 白送）。

6. **组与组名——鉴权硬性禁用组名；展示灵活。** 任何**控制访问**的代码行（API 门禁、可见性、通知路由、按钮显隐）只认 `has_perm`，绝不分支组名。组**名**只作**惰性展示文本**（「所属组: 信息组」是把组当事实显示，不进任何分支）。**徽章不再从组名派生**（见决策 7）。默认组（信息组 / 社长）是迁移播种的**便利起始包**，成员由人手动管，可改名 / 删除 / 替换；没有任何鉴权代码依赖其名字存在。参考实现：`accounts/visibility.py:is_admin_viewer`（持 `news.add_news` 即管理员视角）、`proposals/notifications.py`（按 `groups__permissions__codename` 路由）。

7. **徽章——按身份态四档，与组、权限完全解耦。** 重写 `accounts/views.py:_role_for`（当前按组名字面量 `"社长"` / `"信息组"` 分支——全库唯一组名分支，且改名即坏）。新优先级：

   ```
   is_superuser                           → 超级管理员   （最高，盖一切）
   否则 is_staff                          → 管理员
   否则 已登录且 profile.identity_verified → 用户
   否则（匿名 或 已登录未验证）            → 访客
   ```

   「访客」= 匿名 ∪ 已登录未过身份审核（与 `IsIdentityVerified` 桶一致：未验证 = 还不算正式用户）。在任何展示用户处（`/auth/me/` 自身、他人资料页）统一按此算。`RoleVariant` 改 `visitor | user | admin | superadmin`；`ROLE_BADGE` 配色随之更新；展示顺序：徽章在前、「所属组」列表在后。

8. **读——默认走「身份 + 可见性」，不门禁权限；敏感读才用 `view_*`。** 读的门禁是一档谱系，不是统一的"读权限"：

   ```
   公开（匿名）→ 身份（已登录）→ 可见性过滤（本人 / 管理员）→ 权限门禁（敏感数据, view_*）
   ```

   常规 CRUD 读（news 匿名可读、tasks / proposals 登录可读经 `accounts/visibility.py` 收窄）**不**查 `view` 权限。仅**敏感读**（如 `proposals.view_feedback`——反馈仅社长可见）用专门 `view_*` 权限。原则里的「读」极少指每模型一个 `view` 权限；通常指"已登录 + 可见性放行"。`view` 权限（Django 白送）留作敏感读。

9. **逃生舱——`is_superuser` 是唯一应用访问逃生舱；`is_staff` 在应用访问里零权限。** 超管 `has_perm` 恒真，自动拥有全部能力，无需特判（Django 内建）。`is_staff` 只表示"能登 Django admin"，外加触发「管理员」徽章（展示）——**不**授予任何应用能力。应用访问代码**绝不**读 `is_staff` 做判定。**绝不**新增第二个绕过（如某个"应用管理员组"跳过权限检查）。

## 执行纪律（决策 7 配套）

- **访问控制**（凭角色——*谁*能做 X）→ 命名 DRF `BasePermission` 子类，挂 `permission_classes` / `get_permissions()`。
- **状态机 / 业务规则**（凭状态——*何时*能做 X，如"pending 才能改"）→ 不是访问控制；放视图体或 `tasks/lifecycle.py`。
- 读视图的 `permission_classes` 应能**独立**说明"谁能访问此 action"，不必看函数体。函数体里的内联检查必须是状态机守卫，且**不得**是组检查。
- **现有债**：`tasks/views.py` 有 ~8 处内联 `has_perm("tasks.manage_tasks")`（迁移遗留），按本原则应收口为命名 DRF 类——见待办。

## 被否的方案

逐条 grilling 中被否的 B / C 选项，摘要：

- **所有权也做成权限**（决策 1 的 B）：要么每行 `django-guardian` 对象权限，要么把"创建者"塞进权限——开销大，且与 Django 组 → 权限模型拧着。否。
- **强制自定义读 / 写 / 修改三件套**（决策 2 的 B）：放弃 Django 白送的 CRUD 重造三个——除非领域真能干净映射成 3 类，否则零收益。否。
- **前端直吃原始权限代号**（决策 3 的 B）：SPA 绑死 Django 内部命名，且代号是裸字符串、无法表达"创建者"组合。否。
- **每读都门禁 `view` 权限**（决策 8 的 B）：连公开新闻都要"读权限"，全员配几十个读权限——违背公开内容初衷。否。
- **`is_staff` 也授予应用访问**（决策 9 的 B）：两个逃生舱冗余，且去超管标志留 staff 会静默提权。否。

## 待办（本原则引出的代码债）

1. **重写 `accounts/views.py:_role_for`**（决策 7）——✅ **已完成（2026-08-03）**：改为按 `is_superuser`/`is_staff`/`identity_verified` 派生，去掉组名字面量分支；`accounts/tests.py:RoleForTest` 同步重写。
2. **`frontend/src/types/profile.ts`** 的 `RoleVariant` → `visitor | user | admin | superadmin`；同步 `ROLE_BADGE` 与 `styles/profile.css` 配色——✅ **已完成**。
3. **`PermissionsPanel.tsx`** 重排：徽章在前（ProfileHero）、「所属组」列表置后（panel 末尾）；`CAP_LABELS` 仅作展示层——✅ **已完成**。
4. **契约测试**：后端 `_capabilities` 键集 == 前端 `CAP_LABELS` 键集（决策 4）——✅ **已完成**（`accounts/tests.py:CapabilityKeysContractTest`，已捕获并修复 `can_edit_about` 前端漏显的真实漂移）。
5. ~~收口 `tasks/views.py` 内联 `has_perm`~~——✅ **已满足**：迁移已完成，`tasks/views.py` 0 处内联 `has_perm`（全走 `get_permissions()` + `tasks/lifecycle.py` 集中谓词）。全库复查（2026-08-03）确认**剩余内联 `has_perm` 均合规**——`proposals/views.py:107`（`get_queryset` 反馈可见性过滤，Q8 受限读的规范位置）、`messaging/views.py`（任务/反馈会话的对象级参与 + 权限覆盖，`detail=False` 动作，Q7 例外）、`accounts/views.py:387`（函数视图，无 `permission_classes`）、`accounts/admin.py`（Django admin 原生 `has_perm`）。**全部基于权限判定，无任何组名分支**，无违反原则的散落角色判定。

   > 次要观察（非原则违反，可选清理）：`messaging/views.py:183` 的 `if not user.is_authenticated: return 401` 是死代码（viewset 已 `IsAuthenticated`），可在后续单独清理。
