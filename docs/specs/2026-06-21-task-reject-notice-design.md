# 任务打回提示 — 设计

## 背景与问题

任务完成审核功能上线后，「打回」（`reject_completion`）把任务从「待验收」静默改回「进行中」，负责人不变，没有任何提示。负责人刷新页面后无法区分「被打回」和「正常进行中」，也不知道为什么被打回、要返工什么。

本次需求：任务被打回后给出明确提示，并附带发起人填写的打回理由，让负责人知道需要返工以及返工内容。

## 现状（改造前）

- `reject_completion`（`tasks/views.py`）：`reviewing → in_progress`，`assignee` 不变，前端只 `setTask`，无任何提示。
- `Task` 模型无 reject 相关字段（无理由、无时间）。
- 项目无独立通知系统（有讨论区 + 已读机制，但本次不走讨论区）。

## 已确认决策

- 用「Task 加 `reject_reason` 字段 + 详情横幅 + 列表标记」方案（不走讨论区自动消息）。
- 打回理由**必填**：`reject_completion` 从 `request.data["reason"]` 取，trim 后为空则 400。
- 重新提交验收（`complete`）时**清空** `reject_reason`（表示已按打回意见返工）。
- **不**加打回时间字段（`rejected_at`）、不做打回历史（只保留最新一条）。
- **不**走讨论区（已选字段方案）。

## 目标行为

```
reviewing (待验收)
  │ reject_completion（发起人填理由，必填）
  ▼
in_progress (进行中) + reject_reason="..."   ← 详情横幅「被打回：理由」+ 列表「被打回」徽章
  │ complete（负责人返工后重新提交）
  ▼
reviewing + reject_reason=""                ← 提示消失
```

- 负责人在**任务详情页顶部**看到「⚠ 此任务已被打回：{理由}」横幅（仅 `in_progress` 且 `reject_reason` 非空）。
- **任务列表页**对 `reject_reason` 非空的任务显示「被打回」徽章。
- 发起人点「打回」时弹出/展开理由输入框（textarea，必填），提交后调用 `reject_completion`。

## 后端改动

### `tasks/models.py`
- `Task` 增加：
  ```python
  reject_reason = models.TextField("打回理由", blank=True, default="")
  ```
- 生成 migration：`tasks/0004_task_reject_reason`（仅加一个可空文本字段，无数据迁移）。

### `tasks/views.py`（`TaskViewSet`）
- `reject_completion`：
  - `reason = request.data.get("reason", "").strip()`
  - 若 `not reason` → `400 {"detail": "请填写打回理由"}`
  - 写入 `task.reject_reason = reason`，状态 `reviewing → in_progress`
  - `task.save(update_fields=["status", "reject_reason", "updated_at"])`
- `complete`（重新提交验收）：
  - 状态 `in_progress → reviewing`，同时清空 `task.reject_reason = ""`
  - `task.save(update_fields=["status", "reject_reason", "updated_at"])`
- `approve_completion`：不变（`reviewing → completed`；此时 `reject_reason` 已为空）。
- 权限与状态守卫均不变（`reject_completion`：creator-or-president、必须 `reviewing`）。

### `tasks/serializers.py`
- `TaskListSerializer.Meta.fields` 增加 `"reject_reason"`。
- `TaskDetailSerializer.Meta.fields` 增加 `"reject_reason"`；`read_only_fields` 增加 `"reject_reason"`（该字段只由 `reject_completion`/`complete` action 维护，禁止通过 `update` 写入）。

## 前端改动

### `frontend/src/types/tasks.ts`
- `Task` 与 `TaskDetail` 增加 `reject_reason: string`（可空字符串，默认 `""`）。

### `frontend/src/api/tasks.ts`
- `rejectCompletion(taskId: number, reason: string)` → `POST /tasks/{taskId}/reject_completion/`，body `{ reason }`。
- （路由仍走既有 `BASE = "/tasks"` 双前缀约定，无需改动基础路径。）

### `frontend/src/pages/TaskDetailPage.tsx`
- **打回交互**：点「打回」不再直接提交，改为展开一个理由输入框（textarea，必填）+「确认打回」按钮；提交调用 `rejectCompletion(task.id, reason)`，成功后 `setTask(updated)`，失败显示后端错误。
- **顶部横幅**：当 `task.status === "in_progress" && task.reject_reason` 时，在标题下方显示警告横幅「⚠ 此任务已被打回：{task.reject_reason}」（琥珀/红色调）。

### `frontend/src/pages/TaskListPage.tsx`
- `reject_reason` 非空的任务卡片显示「被打回」徽章。

## 测试（`tasks/tests.py`）

新增 `TaskRejectNoticeTest`：
1. `reject_completion` 带理由 → 状态 `in_progress` 且 `reject_reason` 等于该理由。
2. `reject_completion` 缺 `reason` → 400。
3. `reject_completion` `reason` 为纯空白（仅空格）→ 400。
4. 打回后 `complete`（重新提交）→ `reject_reason` 被清空（`""`）。
5. `approve_completion` 在 `reject_reason` 已空时不受影响（正常 `reviewing → completed`）。

（沿用既有 `APIClient` + `force_authenticate` 写法与双前缀路由。）

## 不在本次范围（YAGNI）

- 打回时间字段（`rejected_at`）与展示。
- 打回历史/留痕（只保留最新一条理由；重新提交即清空）。
- 讨论区自动系统消息（已明确选择字段方案）。
- 社长特殊路径（社长打回同样必填理由，无差异）。
