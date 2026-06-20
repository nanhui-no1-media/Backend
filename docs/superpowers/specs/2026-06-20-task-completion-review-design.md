# 任务完成审核 & 编辑锁定 — 设计

## 背景与问题

两个需求：

1. **完成审核**：任务完成后不应直接进入「已完成」，而要再次进入一个由**任务发起人（creator）**审批的审核状态；发起人可选择「通过」或「打回」。
2. **编辑锁定（bug 修复）**：任务一旦被认领或进入进行中，就不再可通过编辑表单修改。

## 现状（改造前）

状态：`pending`、`in_progress`、`review`、`completed`、`cancelled`。

- `review`（审核中）目前是**认领审批**闸口：用户认领时 `pending → review`，发起人批准认领人 → `in_progress`（拒绝 → 回 `pending`）。
- `complete`：`in_progress → completed`（负责人或社长），写 `completed_at`。
- 编辑（`update` / `partial_update` / `destroy`）：发起人或社长可改，**无状态守卫**——这是 bug。

## 关键约束

「完成审核」不能复用 `review`（已被认领审批占用），必须新增独立状态。

## 已确认决策

- 新增独立状态 `reviewing`（待验收），区别于认领审批的 `review`。
- 「打回」→ 回到 `in_progress`（负责人返工，可再次提交）。
- 编辑锁定：状态离开 `pending` 即对**所有人**锁定，**含社长**。
- 锁定范围仅限 `update` / `partial_update` / `destroy`（编辑表单 + 删除）。工作流动作（`assign`、`approve_claim`、`complete`、`approve_completion`、`reject_completion`、`cancel`）走各自 action，不受影响。

## 目标生命周期

```
pending (待处理)          ← 唯一可编辑状态
  │ claim
  ▼
review (审核中·认领审批)    ← 已锁定
  │ approve_claim
  ▼
in_progress (进行中)       ← 已锁定
  │ complete（负责人提交验收）
  ▼
reviewing (待验收)          ← 已锁定
  │ approve_completion            │ reject_completion（打回）
  ▼                                ▼
completed (已完成)              in_progress（返工，可再次提交）
```

- `completed_at` 仅在「通过验收」时写入；提交与打回均不写。
- 无需 migration：`status` 为 `CharField(max_length=20, choices=...)`，choices 仅应用层校验，DB 无约束；`reviewing`（9 字符）放得下，现有 `completed` 数据不受影响。

## 后端改动

### `tasks/models.py`
- `Task.STATUS_CHOICES` 增加 `("reviewing", "待验收")`。
- 不加字段、不加模型、不加 migration。

### `tasks/views.py`（`TaskViewSet`）
- `complete`：目标由 `completed` 改为 `reviewing`；**不**写 `completed_at`。守卫保持 `status == "in_progress"`，权限保持「负责人或社长」。语义改为「提交验收」，更新 docstring。
- 新增 `approve_completion`（`@action(detail=True, methods=["post"])`）：
  - 守卫 `status == "reviewing"`，否则 400。
  - 权限：`task.creator == user or is_president(user)`，否则 403。
  - 效果：`status = "completed"`，`completed_at = timezone.now()`。
  - 返回 `TaskDetailSerializer`。
- 新增 `reject_completion`（打回，同签名）：
  - 守卫 `status == "reviewing"`，否则 400。
  - 权限：同上（creator or president）。
  - 效果：`status = "in_progress"`（assignee 不变，原负责人继续返工）。
  - 返回 `TaskDetailSerializer`。
- 两个新 action 的鉴权沿用 `approve_claim` 的内联写法（不在 `get_permissions` 中分发）。

### `tasks/permissions.py`（`CanModifyTask`）
```python
def has_object_permission(self, request, view, obj):
    if obj.status != "pending":          # 离开 pending 即对所有人锁定（含社长）
        return False
    if is_president(request.user):
        return True
    return obj.creator == request.user
```
- 该类只作用于 `update` / `partial_update` / `destroy`。

## 前端改动

### `frontend/src/types/tasks.ts`
- `TaskStatus` 增加 `"reviewing"`。
- `STATUS_LABELS`：`reviewing: "待验收"`。
- `STATUS_COLORS`：`reviewing: "#8b5cf6"`（紫色，区别于认领审批的琥珀色 `review`）。

### `frontend/src/api/tasks.ts`
- 新增 `approveCompletion(id)` → `POST /tasks/{id}/approve_completion/`。
- 新增 `rejectCompletion(id)` → `POST /tasks/{id}/reject_completion/`。
- `complete` 无需改动（语义已是提交）。

### `frontend/src/pages/TaskDetailPage.tsx`
- **编辑按钮**（现 line 195）：改为仅当 `task.status === "pending"` 时渲染。
- **修复 `canComplete` bug**（现 line 177）：去掉 `isCreator`，改为 `task.status === "in_progress" && !!isAssignee`（与后端一致；社长由后端兜底）。
- 新增 `canReviewCompletion = task.status === "reviewing" && !!isCreator`。
- 新增 `handleApproveCompletion` / `handleRejectCompletion`（仿 `handleComplete`，调用后 `setTask(updated)`）。
- 动作按钮区（现 line 239–252）：
  - `canComplete`（in_progress 且是负责人）→「提交验收」。
  - `canReviewCompletion`（reviewing 且是发起人）→「通过验收」+「打回」。
  - 保留「取消任务」逻辑不变。
- 状态徽章自动展示新状态（已用 `STATUS_LABELS` / `STATUS_COLORS`）。

### `frontend/src/pages/TaskFormPage.tsx`
- 进入编辑路由时，若 `status !== "pending"`，拦截并提示「该任务当前状态不可编辑」（双保险，后端亦会 403）。

## 测试（`tasks/tests.py`）

新增用例：

1. `complete`：`in_progress → reviewing`，`completed_at` 为空；非 `in_progress` 返回 400。
2. `approve_completion`：`reviewing → completed` 且 `completed_at` 已写入；非发起人/社长 403；非 `reviewing` 状态 400。
3. `reject_completion`：`reviewing → in_progress`；权限同 #2；非 `reviewing` 400。
4. 编辑锁：对 `review` / `in_progress` / `reviewing` / `completed` / `cancelled` 状态执行 `PATCH` / `PUT` / `DELETE`，**含社长**一律 403；仅 `pending` 状态下发起人/社长可改。

## 不在本次范围（YAGNI）

- 审核历史/留痕模型（用任务讨论区代替）。
- 「打回」结构化理由字段（可在讨论区说明；如需再加）。
- 任务列表页对 `reviewing` 的专属文案/筛选（现有按 `status` 过滤已自动支持）。
