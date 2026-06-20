# 任务完成审核 & 编辑锁定 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 任务完成后进入「待验收」状态由发起人审批（通过/打回），并修复任务被认领/进行中后仍可编辑的 bug。

**Architecture:** 新增独立状态 `reviewing`（待验收）。`complete` 改为 `in_progress → reviewing`；新增 `approve_completion`（→ completed）、`reject_completion`（→ in_progress）两个 DRF action。编辑锁定通过 `CanModifyTask.has_object_permission` 加 `status == "pending"` 守卫实现（含社长）。前端加状态展示、动作按钮、编辑入口守卫。

**Tech Stack:** Django 6.0 + DRF（后端），React 19 + TypeScript + Webpack 5（前端）。测试用 `rest_framework.test.APIClient` + `force_authenticate`。

**设计依据:** `docs/superpowers/specs/2026-06-20-task-completion-review-design.md`

---

## 文件结构

| 文件 | 责任 | 动作 |
|------|------|------|
| `tasks/models.py` | `Task.STATUS_CHOICES` 增加 `reviewing` | Modify |
| `tasks/views.py` | `complete` 改为 reviewing；新增 `approve_completion`/`reject_completion` | Modify |
| `tasks/permissions.py` | `CanModifyTask` 加 pending 守卫 | Modify |
| `tasks/tests.py` | 行为测试（当前为空，从零建） | Modify |
| `frontend/src/types/tasks.ts` | `TaskStatus`/标签/颜色加 reviewing | Modify |
| `frontend/src/api/tasks.ts` | 加 `approveCompletion`/`rejectCompletion` | Modify |
| `frontend/src/pages/TaskDetailPage.tsx` | 编辑入口守卫、`canComplete` 修正、审批按钮 | Modify |
| `frontend/src/pages/TaskFormPage.tsx` | 编辑页非 pending 拦截 | Modify |

无需 migration、无需新模型、无需 serializer 改动（`status` 在 `TaskDetailSerializer.Meta.read_only_fields`，仅通过 action 改）。

---

## Task 1: `complete` 提交验收（→ reviewing）+ 新增状态选项

**Files:**
- Modify: `tasks/models.py:29-35`（STATUS_CHOICES）
- Modify: `tasks/views.py:145-157`（complete）
- Modify: `tasks/tests.py`（全量替换，建立测试基线）

- [ ] **Step 1: Write the failing test**

全量替换 `tasks/tests.py` 为：

```python
import json

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Task


def make_president(user):
    """把用户加入「社长」组，使其通过 is_president()。"""
    group, _ = Group.objects.get_or_create(name="社长")
    user.groups.add(group)
    return user


class TaskCompletionReviewTest(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="x")
        self.assignee = User.objects.create_user(username="assignee", password="x")
        self.other = User.objects.create_user(username="other", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        self.task = Task.objects.create(
            title="t", creator=self.creator, assignee=self.assignee, status="in_progress",
        )

    def test_complete_moves_to_reviewing(self):
        self.client.force_authenticate(self.assignee)
        resp = self.client.post(f"/tasks/{self.task.pk}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")
        self.assertIsNone(self.task.completed_at)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python manage.py test tasks.tests.TaskCompletionReviewTest.test_complete_moves_to_reviewing -v 2`
Expected: FAIL — `AssertionError: 'completed' != 'reviewing'`（当前 complete 仍写 completed）。

- [ ] **Step 3: Add the `reviewing` status choice**

在 `tasks/models.py` 的 `STATUS_CHOICES` 增加 `reviewing`（插在 `in_progress` 之后）：

```python
    STATUS_CHOICES = [
        ("pending", "待处理"),
        ("in_progress", "进行中"),
        ("reviewing", "待验收"),
        ("review", "审核中"),
        ("completed", "已完成"),
        ("cancelled", "已取消"),
    ]
```

- [ ] **Step 4: Change `complete` to set `reviewing`**

在 `tasks/views.py` 把 `complete` 改为（不再写 `completed_at`）：

```python
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """提交验收：负责人/社长完成工作，任务进入待验收"""
        task = self.get_object()
        if task.status != "in_progress":
            return Response({"detail": "只有进行中的任务可以提交验收"}, status=status.HTTP_400_BAD_REQUEST)
        if task.assignee != request.user and not is_president(request.user):
            return Response({"detail": "只有负责人或社长可以提交验收"}, status=status.HTTP_403_FORBIDDEN)
        task.status = "reviewing"
        task.save(update_fields=["status", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python manage.py test tasks.tests.TaskCompletionReviewTest.test_complete_moves_to_reviewing -v 2`
Expected: PASS (ok)。

- [ ] **Step 6: Commit**

```bash
git add tasks/models.py tasks/views.py tasks/tests.py
git commit -m "feat(tasks): complete submits for review (in_progress -> reviewing)"
```

---

## Task 2: `approve_completion` action

**Files:**
- Modify: `tasks/views.py`（在 `complete` 之后新增 action）
- Modify: `tasks/tests.py`（`TaskCompletionReviewTest` 内新增三个方法）

- [ ] **Step 1: Write the failing tests**

在 `tasks/tests.py` 的 `TaskCompletionReviewTest` 类内（`test_complete_moves_to_reviewing` 之后）新增：

```python
    def test_approve_completion_by_creator(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/{self.task.pk}/approve_completion/")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "completed")
        self.assertIsNotNone(self.task.completed_at)

    def test_approve_completion_forbidden_for_assignee(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.assignee)
        resp = self.client.post(f"/tasks/{self.task.pk}/approve_completion/")
        self.assertEqual(resp.status_code, 403)

    def test_approve_completion_requires_reviewing(self):
        # setUp 中 task 为 in_progress
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/{self.task.pk}/approve_completion/")
        self.assertEqual(resp.status_code, 400)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python manage.py test tasks.tests.TaskCompletionReviewTest -v 2`
Expected: 三个 approve 测试 FAIL（action 不存在 → 404 或 405，断言 200/403/400 不符）。

- [ ] **Step 3: Implement `approve_completion`**

在 `tasks/views.py` 的 `complete` 方法之后新增：

```python
    @action(detail=True, methods=["post"])
    def approve_completion(self, request, pk=None):
        """通过验收：发起人/社长确认，任务完成"""
        task = self.get_object()
        if task.creator != request.user and not is_president(request.user):
            return Response({"detail": "只有创建者或社长可以审批"}, status=status.HTTP_403_FORBIDDEN)
        if task.status != "reviewing":
            return Response({"detail": "只有待验收的任务可以审批"}, status=status.HTTP_400_BAD_REQUEST)
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python manage.py test tasks.tests.TaskCompletionReviewTest -v 2`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add tasks/views.py tasks/tests.py
git commit -m "feat(tasks): add approve_completion action (reviewing -> completed)"
```

---

## Task 3: `reject_completion`（打回）action

**Files:**
- Modify: `tasks/views.py`（在 `approve_completion` 之后新增）
- Modify: `tasks/tests.py`（`TaskCompletionReviewTest` 内新增三个方法）

- [ ] **Step 1: Write the failing tests**

在 `TaskCompletionReviewTest` 类内追加：

```python
    def test_reject_completion_returns_to_in_progress(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/{self.task.pk}/reject_completion/")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")
        self.assertEqual(self.task.assignee_id, self.assignee.pk)

    def test_reject_completion_forbidden_for_assignee(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.assignee)
        resp = self.client.post(f"/tasks/{self.task.pk}/reject_completion/")
        self.assertEqual(resp.status_code, 403)

    def test_reject_completion_requires_reviewing(self):
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/{self.task.pk}/reject_completion/")
        self.assertEqual(resp.status_code, 400)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python manage.py test tasks.tests.TaskCompletionReviewTest -v 2`
Expected: 三个 reject 测试 FAIL（action 不存在）。

- [ ] **Step 3: Implement `reject_completion`**

在 `tasks/views.py` 的 `approve_completion` 之后新增：

```python
    @action(detail=True, methods=["post"])
    def reject_completion(self, request, pk=None):
        """打回：发起人/社长打回待验收任务，返回进行中（assignee 不变）"""
        task = self.get_object()
        if task.creator != request.user and not is_president(request.user):
            return Response({"detail": "只有创建者或社长可以审批"}, status=status.HTTP_403_FORBIDDEN)
        if task.status != "reviewing":
            return Response({"detail": "只有待验收的任务可以打回"}, status=status.HTTP_400_BAD_REQUEST)
        task.status = "in_progress"
        task.save(update_fields=["status", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python manage.py test tasks.tests.TaskCompletionReviewTest -v 2`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add tasks/views.py tasks/tests.py
git commit -m "feat(tasks): add reject_completion action (打回 -> in_progress)"
```

---

## Task 4: 编辑锁定（`CanModifyTask` 加 pending 守卫）

**Files:**
- Modify: `tasks/permissions.py:28-38`（`CanModifyTask.has_object_permission`）
- Modify: `tasks/tests.py`（新增 `TaskEditLockTest` 类）

- [ ] **Step 1: Write the failing tests**

在 `tasks/tests.py` 末尾新增独立测试类（复用顶部的 `make_president`）：

```python
class TaskEditLockTest(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="x")
        self.president = make_president(User.objects.create_user(username="pres", password="x"))
        self.client = APIClient()
        self.task = Task.objects.create(
            title="t", creator=self.creator, status="in_progress",
        )

    def _patch(self):
        return self.client.patch(
            f"/tasks/{self.task.pk}/",
            data=json.dumps({"title": "changed"}),
            content_type="application/json",
        )

    def test_creator_cannot_edit_in_progress(self):
        self.client.force_authenticate(self.creator)
        self.assertEqual(self._patch().status_code, 403)

    def test_president_cannot_edit_in_progress(self):
        self.client.force_authenticate(self.president)
        self.assertEqual(self._patch().status_code, 403)

    def test_creator_cannot_delete_in_progress(self):
        self.client.force_authenticate(self.creator)
        resp = self.client.delete(f"/tasks/{self.task.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_creator_can_edit_pending(self):
        self.task.status = "pending"
        self.task.save()
        self.client.force_authenticate(self.creator)
        self.assertEqual(self._patch().status_code, 200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python manage.py test tasks.tests.TaskEditLockTest -v 2`
Expected: 前 3 个 FAIL（当前 creator/president 可编辑 in_progress → 返回 200，断言 403 不符）；第 4 个 PASS。

- [ ] **Step 3: Implement the edit lock**

在 `tasks/permissions.py` 把 `CanModifyTask` 改为：

```python
class CanModifyTask(permissions.BasePermission):
    """任务编辑/删除：仅 pending 状态可改；进入认领/进行后对所有人锁定（含社长）"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if obj.status != "pending":
            return False
        if is_president(request.user):
            return True
        return obj.creator == request.user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python manage.py test tasks.tests.TaskEditLockTest -v 2`
Expected: 全部 PASS。

- [ ] **Step 5: Run full task test suite**

Run: `uv run python manage.py test tasks -v 2`
Expected: 全部 PASS（两个类共 11 个测试）。

- [ ] **Step 6: Commit**

```bash
git add tasks/permissions.py tasks/tests.py
git commit -m "fix(tasks): lock editing once task leaves pending (incl. president)"
```

---

## Task 5: 前端类型 + API 客户端

**Files:**
- Modify: `frontend/src/types/tasks.ts:60,104-110,126-132`
- Modify: `frontend/src/api/tasks.ts:62-66`

- [ ] **Step 1: Add `reviewing` to the status type**

`frontend/src/types/tasks.ts:60`：

```typescript
export type TaskStatus = "pending" | "in_progress" | "reviewing" | "review" | "completed" | "cancelled";
```

- [ ] **Step 2: Add label and color**

`STATUS_LABELS`（约 104 行）内加一行：

```typescript
export const STATUS_LABELS: Record<TaskStatus, string> = {
  pending: "待处理",
  in_progress: "进行中",
  reviewing: "待验收",
  review: "审核中",
  completed: "已完成",
  cancelled: "已取消",
};
```

`STATUS_COLORS`（约 126 行）内加一行：

```typescript
export const STATUS_COLORS: Record<TaskStatus, string> = {
  pending: "#6b7280",
  in_progress: "#3b82f6",
  reviewing: "#8b5cf6",
  review: "#f59e0b",
  completed: "#10b981",
  cancelled: "#9ca3af",
};
```

- [ ] **Step 3: Add API methods**

`frontend/src/api/tasks.ts` 的 `// Status` 区块（`complete`/`cancel` 之后）加：

```typescript
  approveCompletion: (taskId: number) =>
    request(`/tasks/${taskId}/approve_completion/`, { method: "POST" }),
  rejectCompletion: (taskId: number) =>
    request(`/tasks/${taskId}/reject_completion/`, { method: "POST" }),
```

- [ ] **Step 4: Typecheck**

Run: `Push-Location frontend; npx tsc --noEmit; $c=$LASTEXITCODE; Pop-Location; exit $c`
Expected: 无输出（退出码 0）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/tasks.ts frontend/src/api/tasks.ts
git commit -m "feat(frontend): add reviewing status and completion-review api methods"
```

---

## Task 6: 前端任务详情页（编辑守卫 + 审批按钮）

**Files:**
- Modify: `frontend/src/pages/TaskDetailPage.tsx`（编辑按钮约 195、canComplete 约 177、动作按钮区约 239-252、新增 handlers）

- [ ] **Step 1: Fix `canComplete` and add `canReviewCompletion`**

`frontend/src/pages/TaskDetailPage.tsx` 约 176-178 行，把：

```typescript
  const canComplete = task && task.status === "in_progress" && (isCreator || isAssignee);
```

改为：

```typescript
  const canComplete = task && task.status === "in_progress" && !!isAssignee;
  const canReviewCompletion = task && task.status === "reviewing" && !!isCreator;
```

- [ ] **Step 2: Add review-completion handlers**

在 `handleComplete`（约 111-122）之后新增：

```typescript
  const handleApproveCompletion = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      const updated = await taskApi.approveCompletion(task.id);
      setTask(updated);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectCompletion = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      const updated = await taskApi.rejectCompletion(task.id);
      setTask(updated);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };
```

- [ ] **Step 3: Update the action buttons row**

约 239-252 行，把整个动作按钮区替换为：

```tsx
        {(canComplete || canReviewCompletion || canCancel) && (
          <div className="task-actions-row">
            {canComplete && (
              <button className="task-btn-primary" onClick={handleComplete} disabled={actionLoading}>
                {actionLoading ? "处理中..." : "提交验收"}
              </button>
            )}
            {canReviewCompletion && (
              <>
                <button className="task-btn-primary" onClick={handleApproveCompletion} disabled={actionLoading}>
                  {actionLoading ? "处理中..." : "通过验收"}
                </button>
                <button className="task-btn-cancel" onClick={handleRejectCompletion} disabled={actionLoading}>
                  打回
                </button>
              </>
            )}
            {canCancel && (
              <button className="task-btn-cancel" onClick={handleCancel} disabled={actionLoading}>
                取消任务
              </button>
            )}
          </div>
        )}
```

- [ ] **Step 4: Guard the edit button**

约 195-197 行，把：

```tsx
          <button className="task-btn-secondary" onClick={() => navigate(`/tasks/${task.id}/edit`)}>
            编辑
          </button>
```

改为：

```tsx
          {task.status === "pending" && (
            <button className="task-btn-secondary" onClick={() => navigate(`/tasks/${task.id}/edit`)}>
              编辑
            </button>
          )}
```

- [ ] **Step 5: Typecheck**

Run: `Push-Location frontend; npx tsc --noEmit; $c=$LASTEXITCODE; Pop-Location; exit $c`
Expected: 无输出（退出码 0）。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/TaskDetailPage.tsx
git commit -m "feat(frontend): completion-review buttons + edit lock on detail page"
```

---

## Task 7: 前端编辑页非 pending 拦截

**Files:**
- Modify: `frontend/src/pages/TaskFormPage.tsx`

- [ ] **Step 1: Add `blocked` state**

`frontend/src/pages/TaskFormPage.tsx` 约 25 行（`error` state 附近）加：

```typescript
  const [blocked, setBlocked] = useState(false);
```

- [ ] **Step 2: Set blocked when loading a non-pending task**

约 47-61 行，把编辑态加载逻辑改为（在 set 字段前判断）：

```typescript
  useEffect(() => {
    if (!isEdit) return;
    setLoading(true);
    taskApi.get(Number(id))
      .then((task: TaskDetail) => {
        if (task.status !== "pending") {
          setBlocked(true);
          return;
        }
        setTitle(task.title);
        setDescription(task.description);
        setPriority(task.priority);
        setAssigneeId(task.assignee?.id || "");
        setTagIds(task.tags.map((t) => t.id));
        setCollaboratorIds(task.collaborators.map((c) => c.id));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, isEdit]);
```

- [ ] **Step 3: Render a block message when blocked**

约 105 行（`if (loading) return ...`）之后加：

```tsx
  if (blocked) {
    return (
      <div className="task-page">
        <div className="task-form-container">
          <div className="task-error">该任务当前状态不可编辑</div>
          <button className="task-btn-secondary" onClick={() => navigate(`/tasks/${id}`)}>
            返回详情
          </button>
        </div>
      </div>
    );
  }
```

- [ ] **Step 4: Typecheck**

Run: `Push-Location frontend; npx tsc --noEmit; $c=$LASTEXITCODE; Pop-Location; exit $c`
Expected: 无输出（退出码 0）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/TaskFormPage.tsx
git commit -m "feat(frontend): block editing form for non-pending tasks"
```

---

## Task 8: 重新构建前端并验证

**Files:** 无源码改动（构建产物 `frontend/dist/`）

- [ ] **Step 1: Run the backend test suite once more**

Run: `uv run python manage.py test tasks -v 2`
Expected: 全部 PASS（11 个测试）。

- [ ] **Step 2: Rebuild the frontend**

Run: `Push-Location frontend; npm run build; $c=$LASTEXITCODE; Pop-Location; exit $c`
Expected: `webpack ... compiled ... in ...` + 退出码 0。

- [ ] **Step 3: Verify Django serves the fresh build**

Run:
```powershell
$r = Invoke-WebRequest http://127.0.0.1:8000/ -UseBasicParsing
"status: $($r.StatusCode)"
```
Expected: `status: 200`（Django 正在运行时）。

- [ ] **Step 4: Manual verification（需 Django + 浏览器）**

1. 负责人在 `in_progress` 任务点「提交验收」→ 状态变「待验收」，地址栏 `/#/tasks/<id>`，刷新不再 404。
2. 发起人在「待验收」任务看到「通过验收」+「打回」。
3. 点「通过验收」→「已完成」；点「打回」→ 回「进行中」，负责人不变。
4. 非 `pending` 状态任务：详情页无「编辑」按钮；直接访问 `/#/tasks/<id>/edit` 显示「不可编辑」。
5. `pending` 状态：发起人可正常编辑。

- [ ] **Step 5: Commit build note（可选）**

若 `frontend/dist/` 不在 git 忽略则提交；否则跳过。本任务无源码改动，通常无需 commit。

---

## 完成标准

- 后端 11 个测试全绿（`complete`→reviewing、`approve_completion`、`reject_completion`、编辑锁 4 例）。
- 前端 `tsc --noEmit` 通过。
- 浏览器手动走查 5 项行为通过。
- 生命周期：`pending → review → in_progress → reviewing → completed`（打回回 `in_progress`）；仅 `pending` 可编辑。
