# 任务打回提示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 任务被打回后，把发起人填写的打回理由持久化到 `Task.reject_reason`，并在任务详情页顶部横幅、任务列表页徽章中提示负责人返工；重新提交验收时清空。

**Architecture:** 后端给 `Task` 加一个可空 `reject_reason` 文本字段（+ migration），`reject_completion` 必填并写入理由，`complete` 清空理由，两个序列化器暴露该字段（只读）。前端在类型/API/详情页（理由输入框 + 横幅）/列表页（徽章）渲染。纯增量，不改状态机。

**Tech Stack:** Django 6.0 + DRF（后端），React 19 + TypeScript + Webpack 5（前端），`uv` / `npm`。

---

## 关键约定（不要"修复"）

- **路由双前缀是既定契约**：`config/urls.py` 挂 `path('tasks/', include('tasks.urls'))`，而 `tasks/urls.py` 又注册 `router.register(r"tasks", TaskViewSet)`，所以真实路由是 `/tasks/tasks/{pk}/...`。前端 `frontend/src/api/tasks.ts` 用 `BASE="/tasks"` + `/tasks/{id}/...` 路径，正是为了命中这个双前缀。**测试 URL 必须用 `/tasks/tasks/{pk}/...`，前端 API 路径必须保持 `/tasks/{id}/...`。不要改路由。**
- 测试用 `rest_framework.test.APIClient` + `force_authenticate(user)`（绕过认证，但权限仍执行）。`is_president(user)` 判断 Django Group「社长」。helper `make_president(user)` 已存在于 `tasks/tests.py`。
- 后端命令前缀 `uv run python manage.py ...`；前端构建在 `frontend/` 目录 `npm run build`。
- 提交信息用 conventional commits（`feat:` / `docs:` 等）。

---

## 文件结构

- `tasks/models.py` — `Task` 增加 `reject_reason` 字段。
- `tasks/migrations/0004_task_reject_reason.py` — 自动生成（仅加可空文本字段）。
- `tasks/views.py` — `reject_completion` 必填并写入理由；`complete` 清空理由。
- `tasks/serializers.py` — `TaskListSerializer` / `TaskDetailSerializer` 暴露 `reject_reason`（只读）。
- `tasks/tests.py` — 新增 `TaskRejectNoticeTest`；更新一处既有用例。
- `frontend/src/types/tasks.ts` — `TaskListItem` / `TaskDetail` 增加 `reject_reason`。
- `frontend/src/api/tasks.ts` — `rejectCompletion(taskId, reason)`。
- `frontend/src/pages/TaskDetailPage.tsx` — 打回理由输入框 + 顶部横幅。
- `frontend/src/pages/TaskListPage.tsx` — 「被打回」徽章。

---

## Task 1: Task.reject_reason 字段 + migration + 序列化器暴露

**Files:**
- Modify: `tasks/models.py:64`（在 `completed_at` 之后加字段）
- Create: `tasks/migrations/0004_task_reject_reason.py`（由 makemigrations 生成）
- Modify: `tasks/serializers.py:76-82`（`TaskListSerializer.Meta.fields`）、`tasks/serializers.py:111-120`（`TaskDetailSerializer.Meta`）
- Test: `tasks/tests.py`（新增 `TaskRejectNoticeTest` 类 + 一个用例）

- [ ] **Step 1: 给 Task 加字段**

在 `tasks/models.py` 的 `completed_at` 字段（第 64 行）之后插入：

```python
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    reject_reason = models.TextField("打回理由", blank=True, default="")
```

- [ ] **Step 2: 生成 migration**

Run: `uv run python manage.py makemigrations tasks`
Expected: `Migrations for 'tasks': tasks/migrations/0004_task_reject_reason.py - Add field reject_reason to task`

- [ ] **Step 3: 应用 migration 并校验**

Run: `uv run python manage.py migrate`
Expected: `Applying tasks.0004_task_reject_reason... OK`

Run: `uv run python manage.py check`
Expected: `System check identified no issues. (0 silenced).`

- [ ] **Step 4: 写失败测试（序列化器未暴露字段）**

在 `tasks/tests.py` 末尾新增测试类（`setUp` 建一个 reviewing 状态的任务）：

```python
class TaskRejectNoticeTest(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator2", password="x")
        self.assignee = User.objects.create_user(username="assignee2", password="x")
        self.client = APIClient()
        self.task = Task.objects.create(
            title="t", creator=self.creator, assignee=self.assignee, status="reviewing",
        )

    def test_detail_includes_reject_reason(self):
        self.task.reject_reason = "需补充截图"
        self.task.save()
        self.client.force_authenticate(self.creator)
        resp = self.client.get(f"/tasks/tasks/{self.task.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["reject_reason"], "需补充截图")
```

- [ ] **Step 5: 运行测试，确认失败**

Run: `uv run python manage.py test tasks.TaskRejectNoticeTest.test_detail_includes_reject_reason -v 2`
Expected: FAIL（`KeyError: 'reject_reason'`，因为序列化器还没暴露该字段）。

- [ ] **Step 6: 序列化器暴露 reject_reason**

修改 `tasks/serializers.py` 的 `TaskListSerializer.Meta.fields`（第 76-82 行），加入 `"reject_reason"`：

```python
        fields = [
            "id", "title", "status", "priority",
            "creator", "assignee", "tags",
            "completed_at",
            "reject_reason",
            "attachment_count",
            "created_at", "updated_at",
        ]
```

修改 `TaskDetailSerializer.Meta`（第 111-120 行），`fields` 加入 `"reject_reason"`，`read_only_fields` 也加入 `"reject_reason"`：

```python
        fields = [
            "id", "title", "description", "status", "priority",
            "creator", "assignee", "assignee_id",
            "collaborators", "collaborator_ids",
            "tags", "tag_ids",
            "attachments", "claim_requests",
            "completed_at",
            "reject_reason",
            "created_at", "updated_at",
        ]
        read_only_fields = ["creator", "status", "completed_at", "reject_reason", "created_at", "updated_at"]
```

- [ ] **Step 7: 运行测试，确认通过**

Run: `uv run python manage.py test tasks.TaskRejectNoticeTest -v 2`
Expected: PASS（1 个用例）。

- [ ] **Step 8: 提交**

```bash
git add tasks/models.py tasks/migrations/0004_task_reject_reason.py tasks/serializers.py tasks/tests.py
git commit -m "feat: add reject_reason field to Task with serializer exposure"
```

---

## Task 2: reject_completion 必填并写入理由

**Files:**
- Modify: `tasks/views.py:170-180`（`reject_completion`）
- Test: `tasks/tests.py`（`TaskRejectNoticeTest` 加 3 个用例；更新 `TaskCompletionReviewTest.test_reject_completion_returns_to_in_progress`）

- [ ] **Step 1: 写失败测试**

在 `TaskRejectNoticeTest` 中追加 3 个用例：

```python
    def test_reject_completion_writes_reason(self):
        self.client.force_authenticate(self.creator)
        resp = self.client.post(
            f"/tasks/tasks/{self.task.pk}/reject_completion/",
            data=json.dumps({"reason": "需补充截图"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")
        self.assertEqual(self.task.reject_reason, "需补充截图")

    def test_reject_completion_requires_reason(self):
        self.client.force_authenticate(self.creator)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/reject_completion/")
        self.assertEqual(resp.status_code, 400)

    def test_reject_completion_blank_reason_rejected(self):
        self.client.force_authenticate(self.creator)
        resp = self.client.post(
            f"/tasks/tasks/{self.task.pk}/reject_completion/",
            data=json.dumps({"reason": "   "}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
```

同时**更新既有用例** `TaskCompletionReviewTest.test_reject_completion_returns_to_in_progress`（`tasks/tests.py:59-67`）——它原本不带 body 提交打回，新逻辑下会 400，必须改成带理由，并断言理由已写入：

```python
    def test_reject_completion_returns_to_in_progress(self):
        self.task.status = "reviewing"
        self.task.save()
        self.client.force_authenticate(self.creator)
        resp = self.client.post(
            f"/tasks/tasks/{self.task.pk}/reject_completion/",
            data=json.dumps({"reason": "返工"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")
        self.assertEqual(self.task.assignee_id, self.assignee.pk)
        self.assertEqual(self.task.reject_reason, "返工")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run python manage.py test tasks.TaskRejectNoticeTest tasks.TaskCompletionReviewTest.test_reject_completion_returns_to_in_progress -v 2`
Expected: FAIL（`writes_reason` 与更新后的既有用例断言 `reject_reason` 为空；`requires_reason` / `blank_reason_rejected` 收到 200 而非 400）。

- [ ] **Step 3: 实现 reject_completion 必填并写入理由**

把 `tasks/views.py:170-180` 的 `reject_completion` 替换为：

```python
    @action(detail=True, methods=["post"])
    def reject_completion(self, request, pk=None):
        """打回：发起人/社长打回待验收任务，返回进行中（assignee 不变，记录打回理由）"""
        task = self.get_object()
        if task.creator != request.user and not is_president(request.user):
            return Response({"detail": "只有创建者或社长可以审批"}, status=status.HTTP_403_FORBIDDEN)
        if task.status != "reviewing":
            return Response({"detail": "只有待验收的任务可以打回"}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"detail": "请填写打回理由"}, status=status.HTTP_400_BAD_REQUEST)
        task.status = "in_progress"
        task.reject_reason = reason
        task.save(update_fields=["status", "reject_reason", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `uv run python manage.py test tasks -v 2`
Expected: PASS（全部 tasks 用例，含新增 4 个 + 更新 1 个）。

- [ ] **Step 5: 提交**

```bash
git add tasks/views.py tasks/tests.py
git commit -m "feat: reject_completion requires and records reason"
```

---

## Task 3: complete 清空 reject_reason

**Files:**
- Modify: `tasks/views.py:145-155`（`complete`）
- Test: `tasks/tests.py`（`TaskRejectNoticeTest` 加 1 个用例）

- [ ] **Step 1: 写失败测试**

在 `TaskRejectNoticeTest` 中追加：

```python
    def test_complete_clears_reject_reason(self):
        # 模拟已被打回：回到进行中且带理由
        self.task.status = "in_progress"
        self.task.reject_reason = "需补充截图"
        self.task.save()
        self.client.force_authenticate(self.assignee)
        resp = self.client.post(f"/tasks/tasks/{self.task.pk}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")
        self.assertEqual(self.task.reject_reason, "")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run python manage.py test tasks.TaskRejectNoticeTest.test_complete_clears_reject_reason -v 2`
Expected: FAIL（`reject_reason` 仍为 `"需补充截图"`，因为 `complete` 还没清空）。

- [ ] **Step 3: 实现 complete 清空理由**

把 `tasks/views.py:145-155` 的 `complete` 替换为：

```python
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """提交验收：负责人/社长完成工作，任务进入待验收（清空打回理由）"""
        task = self.get_object()
        if task.status != "in_progress":
            return Response({"detail": "只有进行中的任务可以提交验收"}, status=status.HTTP_400_BAD_REQUEST)
        if task.assignee != request.user and not is_president(request.user):
            return Response({"detail": "只有负责人或社长可以提交验收"}, status=status.HTTP_403_FORBIDDEN)
        task.status = "reviewing"
        task.reject_reason = ""
        task.save(update_fields=["status", "reject_reason", "updated_at"])
        return Response(TaskDetailSerializer(task, context={"request": request}).data)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `uv run python manage.py test tasks -v 2`
Expected: PASS（全部 tasks 用例）。

- [ ] **Step 5: 提交**

```bash
git add tasks/views.py tasks/tests.py
git commit -m "feat: clear reject_reason on resubmit (complete)"
```

---

## Task 4: 前端类型 + API 客户端

**Files:**
- Modify: `frontend/src/types/tasks.ts:63-75`（`TaskListItem`）、`frontend/src/types/tasks.ts:77-92`（`TaskDetail`）
- Modify: `frontend/src/api/tasks.ts:69-70`（`rejectCompletion`）

- [ ] **Step 1: 类型加 reject_reason**

在 `frontend/src/types/tasks.ts` 的 `TaskListItem`（第 63-75 行）中，`completed_at` 之后加一行：

```typescript
export interface TaskListItem {
  id: number;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  creator: TaskUser;
  assignee: TaskUser | null;
  tags: Tag[];
  completed_at: string | null;
  reject_reason: string;
  attachment_count: number;
  created_at: string;
  updated_at: string;
}
```

在 `TaskDetail`（第 77-92 行）中，`completed_at` 之后加一行：

```typescript
export interface TaskDetail {
  id: number;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  creator: TaskUser;
  assignee: TaskUser | null;
  collaborators: TaskUser[];
  tags: Tag[];
  attachments: Attachment[];
  claim_requests: TaskClaimRequest[];
  completed_at: string | null;
  reject_reason: string;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: API 加 reason 参数**

把 `frontend/src/api/tasks.ts:69-70` 的 `rejectCompletion` 替换为（接受 reason，走既有双前缀路径）：

```typescript
  rejectCompletion: (taskId: number, reason: string) =>
    request(`/tasks/${taskId}/reject_completion/`, { method: "POST", body: JSON.stringify({ reason }) }),
```

- [ ] **Step 3: 构建校验（类型 + 编译）**

Run（在 `frontend/` 目录）: `npm run build`
Expected: `webpack ... compiled ... in ...` 成功（仅有资源体积 warning，无 error）。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/tasks.ts frontend/src/api/tasks.ts
git commit -m "feat: expose reject_reason in frontend types and api"
```

---

## Task 5: 任务详情页 — 打回理由输入框 + 顶部横幅

**Files:**
- Modify: `frontend/src/pages/TaskDetailPage.tsx`（state、`handleRejectCompletion`、按钮、横幅、理由表单）

- [ ] **Step 1: 加 state**

在 `TaskDetailPage.tsx` 第 26 行（`currentUser` state）之后插入两个 state：

```typescript
  const [currentUser, setCurrentUser] = useState<{ id: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
```

- [ ] **Step 2: 改 handleRejectCompletion 读取理由**

把第 137-148 行的 `handleRejectCompletion` 替换为（从 `rejectReason` 取值，前端先做非空校验，成功后复位表单）：

```typescript
  const handleRejectCompletion = async () => {
    if (!task) return;
    const reason = rejectReason.trim();
    if (!reason) {
      setError("请填写打回理由");
      return;
    }
    setActionLoading(true);
    try {
      const updated = await taskApi.rejectCompletion(task.id, reason);
      setTask(updated);
      setShowRejectForm(false);
      setRejectReason("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };
```

- [ ] **Step 3: 顶部横幅（被打回提示）**

在标题行 `task-detail-title-row` 的 `</div>`（第 246 行）之后、`task-detail-meta`（第 248 行）之前插入横幅（仅 `in_progress` 且有理由时显示，用内联样式，琥珀警告色）：

```tsx
        </div>

        {task.status === "in_progress" && task.reject_reason && (
          <div
            style={{
              backgroundColor: "#fef3c7",
              color: "#92400e",
              border: "1px solid #f59e0b",
              borderRadius: "8px",
              padding: "10px 14px",
              margin: "12px 0",
              fontSize: "14px",
              lineHeight: 1.5,
            }}
          >
            ⚠ 此任务已被打回：{task.reject_reason}
          </div>
        )}

        <div className="task-detail-meta">
```

- [ ] **Step 4: 打回按钮改为打开理由表单**

把动作按钮区里的打回按钮（第 280-282 行）改为打开表单（不再直接提交）：

```tsx
                <button className="task-btn-cancel" onClick={() => setShowRejectForm(true)} disabled={actionLoading}>
                  打回
                </button>
```

- [ ] **Step 5: 理由输入表单**

在动作按钮区 `task-actions-row` 的闭合 `</div>`（第 291 行）之后、`task.tags.length > 0` 区块（第 293 行）之前，插入理由表单（复用 `.claim-form` 样式，含确认/取消）：

```tsx
        )}

        {showRejectForm && canReviewCompletion && (
          <div className="task-detail-section">
            <h3>打回理由</h3>
            <div className="claim-form">
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="说明打回原因，告知负责人需返工的内容..."
                rows={3}
              />
              <button className="task-btn-primary" onClick={handleRejectCompletion} disabled={actionLoading}>
                {actionLoading ? "处理中..." : "确认打回"}
              </button>
              <button
                className="task-btn-secondary"
                onClick={() => { setShowRejectForm(false); setRejectReason(""); }}
                disabled={actionLoading}
              >
                取消
              </button>
            </div>
          </div>
        )}

        {task.tags.length > 0 && (
```

- [ ] **Step 6: 构建校验**

Run（在 `frontend/` 目录）: `npm run build`
Expected: 编译成功（仅资源体积 warning）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/pages/TaskDetailPage.tsx
git commit -m "feat: show reject banner and reason input on task detail"
```

---

## Task 6: 任务列表页 — 「被打回」徽章

**Files:**
- Modify: `frontend/src/pages/TaskListPage.tsx:148-149`（状态徽章之后加「被打回」徽章）

- [ ] **Step 1: 加徽章**

在 `TaskListPage.tsx` 的任务卡片 meta 区里，状态徽章 `<span className="task-status-badge">...</span>`（第 141-149 行）之后、`task.tags.map`（第 150 行）之前，插入「被打回」徽章（有理由才显示，复用 `task-status-badge` 类 + 琥珀色）：

```tsx
                        <span
                          className="task-status-badge"
                          style={{
                            backgroundColor: STATUS_COLORS[task.status] + "18",
                            color: STATUS_COLORS[task.status],
                          }}
                        >
                          {STATUS_LABELS[task.status]}
                        </span>
                        {task.reject_reason && (
                          <span
                            className="task-status-badge"
                            style={{ backgroundColor: "#fef3c7", color: "#92400e" }}
                          >
                            被打回
                          </span>
                        )}
                        {task.tags.map((t) => (
```

- [ ] **Step 2: 构建校验**

Run（在 `frontend/` 目录）: `npm run build`
Expected: 编译成功（仅资源体积 warning）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/TaskListPage.tsx
git commit -m "feat: show 被打回 badge on task list"
```

---

## Task 7: 重新构建并验证

**Files:** 无（仅构建与验证）

- [ ] **Step 1: 重新构建前端产物**

Run（在 `frontend/` 目录）: `npm run build`
Expected: 编译成功，产物写入 `frontend/dist/`。

- [ ] **Step 2: 启动 Django 并确认提供新构建**

Run（仓库根目录，后台）: `uv run python manage.py runserver 127.0.0.1:8765 --noreload`

确认根路径返回 200 且引用新 bundle：
```bash
curl -s -o /tmp/idx.html -w "HTTP %{http_code}\n" http://127.0.0.1:8765/
grep -oE 'main\.[a-f0-9]+\.js' /tmp/idx.html | head -1
```
Expected: `HTTP 200` + 一个 `main.<hash>.js`。

确认详情页懒加载 chunk 含「被打回」「打回理由」等新文案（chunk 文件名从 `main.<hash>.js` 的 `i.u` 映射里取 TaskDetailPage 的 chunk，如 `631.<hash>.chunk.js`）：
```bash
# 用上一步读到的 detail chunk 文件名
curl -s http://127.0.0.1:8765/static/<detail-chunk>.chunk.js | grep -o "此任务已被打回\|打回理由\|确认打回" | sort -u
```
Expected: 至少出现 `此任务已被打回`、`打回理由`、`确认打回`。

- [ ] **Step 3: 跑完整后端测试**

Run: `uv run python manage.py test tasks -v 2`
Expected: 全部通过（原 11 个 + 新增 5 个 = 16 个）。

- [ ] **Step 4: 停止 dev server**

停止 Task 7 Step 2 启动的后台 runserver。

- [ ] **Step 5: 人工浏览器验证清单（交给用户）**

1. 进行中任务 → 负责人「提交验收」→ 待验收 → 发起人点「打回」→ 弹出理由框，**不填理由**确认 → 报错（前端提示/后端 400）。
2. 填理由「需补充截图」→ 确认打回 → 状态回「进行中」，详情页顶部出现琥珀横幅「⚠ 此任务已被打回：需补充截图」。
3. 任务列表该任务显示「被打回」徽章。
4. 负责人返工后「提交验收」→ 横幅与徽章消失（reject_reason 清空）。
5. 非发起人（如负责人）在待验收时看不到打回按钮。

---

## Self-Review

**1. Spec 覆盖：**
- `Task.reject_reason` 字段 + migration → Task 1 ✅
- `reject_completion` 必填理由、写入 → Task 2 ✅
- `complete` 清空理由 → Task 3 ✅
- 序列化器暴露（详情 + 列表，只读）→ Task 1 Step 6 ✅
- 前端类型 → Task 4 ✅；API `rejectCompletion(id, reason)` → Task 4 ✅
- 详情页理由输入框 + 顶部横幅 → Task 5 ✅
- 列表页「被打回」徽章 → Task 6 ✅
- 测试（5 个新用例 + 1 处既有更新）→ Task 1/2/3 ✅
- YAGNI（无时间字段、无历史、不走讨论区）→ 全程未引入 ✅

**2. 占位符扫描：** 无 TBD/TODO；每步都给了完整代码或确切命令。✅

**3. 类型一致性：** `reject_reason` 在 model / 两个 serializer / `TaskListItem` / `TaskDetail` / API 签名（`(taskId, reason)`）/ handler 中命名与类型一致；前端 `taskApi.rejectCompletion(task.id, reason)` 与 API 定义一致；测试断言键名 `reject_reason` 与序列化器字段一致。✅

**4. 既有用例回归：** `test_reject_completion_returns_to_in_progress` 原不带 body，Task 2 Step 1 已更新为带理由 + 断言写入，避免新逻辑下 400。✅
