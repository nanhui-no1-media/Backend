# Task Timeline & Gantt Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove start_date/due_date from the task system, replace with automatic created_at/completed_at tracking, and add Timeline and Gantt Chart views to the task list page.

**Architecture:** Backend removes two manual date fields from the Task model, serializers, and views. Frontend removes corresponding form inputs and displays, then adds two new view-mode components (Timeline via pure CSS, Gantt via frappe-gantt library) with a view toggle on the task list page.

**Tech Stack:** Django 6.0 + DRF (backend), React 19 + TypeScript + Webpack 5 (frontend), frappe-gantt (Gantt chart library)

---

## Task 1: Remove start_date and due_date from backend model

**Files:**
- Modify: `tasks/models.py:63-64`

- [ ] **Step 1: Remove the two date fields from Task model**

In `tasks/models.py`, remove lines 63-64 (the `start_date` and `due_date` fields):

```python
# DELETE these two lines:
    start_date = models.DateField("开始日期", null=True, blank=True)
    due_date = models.DateField("截止日期", null=True, blank=True)
```

The model should go directly from the `collaborators` field to `completed_at`.

- [ ] **Step 2: Generate migration**

Run: `uv run python manage.py makemigrations tasks`
Expected: Creates a new migration file that removes `start_date` and `due_date` from the `tasks_task` table.

- [ ] **Step 3: Apply migration**

Run: `uv run python manage.py migrate`
Expected: `Running migrations: tasks/... OK`

- [ ] **Step 4: Commit**

```bash
git add tasks/models.py tasks/migrations/
git commit -m "refactor: remove start_date and due_date from Task model"
```

---

## Task 2: Remove start_date and due_date from serializers

**Files:**
- Modify: `tasks/serializers.py:79-80` (TaskListSerializer fields)
- Modify: `tasks/serializers.py:117` (TaskDetailSerializer fields)

- [ ] **Step 1: Update TaskListSerializer fields**

In `tasks/serializers.py`, the `TaskListSerializer.Meta.fields` list (around line 79) currently includes `"start_date"` and `"due_date"`. Remove both:

```python
# BEFORE:
        fields = [
            "id", "title", "status", "priority",
            "creator", "assignee", "tags",
            "start_date", "due_date", "completed_at",
            "attachment_count",
            "created_at", "updated_at",
        ]

# AFTER:
        fields = [
            "id", "title", "status", "priority",
            "creator", "assignee", "tags",
            "completed_at",
            "attachment_count",
            "created_at", "updated_at",
        ]
```

- [ ] **Step 2: Update TaskDetailSerializer fields**

In the same file, the `TaskDetailSerializer.Meta.fields` list (around line 117) also includes `"start_date"` and `"due_date"`. Remove both:

```python
# BEFORE:
        fields = [
            "id", "title", "description", "status", "priority",
            "creator", "assignee", "assignee_id",
            "collaborators", "collaborator_ids",
            "tags", "tag_ids",
            "attachments", "claim_requests",
            "start_date", "due_date", "completed_at",
            "created_at", "updated_at",
        ]

# AFTER:
        fields = [
            "id", "title", "description", "status", "priority",
            "creator", "assignee", "assignee_id",
            "collaborators", "collaborator_ids",
            "tags", "tag_ids",
            "attachments", "claim_requests",
            "completed_at",
            "created_at", "updated_at",
        ]
```

- [ ] **Step 3: Verify Django check passes**

Run: `uv run python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add tasks/serializers.py
git commit -m "refactor: remove start_date and due_date from task serializers"
```

---

## Task 3: Update view ordering_fields

**Files:**
- Modify: `tasks/views.py:48`

- [ ] **Step 1: Update ordering_fields in TaskViewSet**

In `tasks/views.py`, line 48, replace `due_date` with `completed_at` in `ordering_fields`:

```python
# BEFORE:
    ordering_fields = ["created_at", "due_date", "priority", "status"]

# AFTER:
    ordering_fields = ["created_at", "completed_at", "priority", "status"]
```

- [ ] **Step 2: Verify Django check passes**

Run: `uv run python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add tasks/views.py
git commit -m "refactor: update task ordering_fields to use completed_at"
```

---

## Task 4: Remove date fields from frontend types

**Files:**
- Modify: `frontend/src/types/tasks.ts:71-72` (TaskListItem)
- Modify: `frontend/src/types/tasks.ts:91-92` (TaskDetail)
- Modify: `frontend/src/types/tasks.ts:106-107` (TaskFormData)

- [ ] **Step 1: Remove fields from TaskListItem interface**

In `frontend/src/types/tasks.ts`, remove `start_date` and `due_date` from `TaskListItem`:

```typescript
// BEFORE (lines 63-77):
export interface TaskListItem {
  id: number;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  creator: TaskUser;
  assignee: TaskUser | null;
  tags: Tag[];
  start_date: string | null;
  due_date: string | null;
  completed_at: string | null;
  attachment_count: number;
  created_at: string;
  updated_at: string;
}

// AFTER:
export interface TaskListItem {
  id: number;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  creator: TaskUser;
  assignee: TaskUser | null;
  tags: Tag[];
  completed_at: string | null;
  attachment_count: number;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Remove fields from TaskDetail interface**

Remove `start_date` and `due_date` from `TaskDetail`:

```typescript
// BEFORE (lines 79-96):
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
  start_date: string | null;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// AFTER:
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
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 3: Remove fields from TaskFormData interface**

Remove `start_date` and `due_date` from `TaskFormData`:

```typescript
// BEFORE (lines 98-108):
export interface TaskFormData {
  title: string;
  description: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: number | null;
  collaborator_ids?: number[];
  tag_ids?: number[];
  start_date?: string | null;
  due_date?: string | null;
}

// AFTER:
export interface TaskFormData {
  title: string;
  description: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: number | null;
  collaborator_ids?: number[];
  tag_ids?: number[];
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/tasks.ts
git commit -m "refactor: remove start_date and due_date from frontend task types"
```

---

## Task 5: Remove date inputs from TaskFormPage

**Files:**
- Modify: `frontend/src/pages/TaskFormPage.tsx`

- [ ] **Step 1: Remove date state variables**

Remove the two state declarations (around line 33-34):

```typescript
// DELETE these lines:
  const [startDate, setStartDate] = useState("");
  const [dueDate, setDueDate] = useState("");
```

- [ ] **Step 2: Remove date field population in edit useEffect**

In the edit-mode `useEffect` (around lines 60-61), remove the two date setter calls:

```typescript
// DELETE these lines from the .then() callback:
        setStartDate(task.start_date || "");
        setDueDate(task.due_date || "");
```

- [ ] **Step 3: Remove date assignments from handleSubmit**

In `handleSubmit` (around lines 92-93), remove the date field assignments from the `data` object:

```typescript
// BEFORE:
    const data: TaskFormData = {
      title: title.trim(),
      description,
      priority,
      start_date: startDate || null,
      due_date: dueDate || null,
    };

// AFTER:
    const data: TaskFormData = {
      title: title.trim(),
      description,
      priority,
    };
```

- [ ] **Step 4: Remove the date picker form row**

Remove the entire `<div className="form-row">` block containing the date inputs (around lines 161-169):

```tsx
// DELETE this entire block:
          <div className="form-row">
            <div className="form-field">
              <label>开始日期</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="form-field">
              <label>截止日期</label>
              <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
          </div>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/TaskFormPage.tsx
git commit -m "refactor: remove date inputs from task form"
```

---

## Task 6: Remove date display from TaskDetailPage

**Files:**
- Modify: `frontend/src/pages/TaskDetailPage.tsx:232-239`

- [ ] **Step 1: Remove the two date meta-items**

Remove the "开始日期" and "截止日期" meta items from the metadata grid (around lines 232-239):

```tsx
// DELETE these two meta-item blocks:
          <div className="meta-item">
            <span className="meta-label">开始日期</span>
            <span>{formatDate(task.start_date)}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">截止日期</span>
            <span>{formatDate(task.due_date)}</span>
          </div>
```

The "创建时间" meta-item that follows should remain unchanged.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/TaskDetailPage.tsx
git commit -m "refactor: remove start/due date display from task detail"
```

---

## Task 7: Remove due_date from TaskListPage cards

**Files:**
- Modify: `frontend/src/pages/TaskListPage.tsx:139`

- [ ] **Step 1: Remove due_date display from task card**

Remove the due date span from the card meta area (around line 139):

```tsx
// DELETE this line:
                      <span className="task-meta-text">{formatDate(task.due_date)}</span>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/TaskListPage.tsx
git commit -m "refactor: remove due_date from task list cards"
```

---

## Task 8: Install frappe-gantt

**Files:**
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Install frappe-gantt**

Run: `cd frontend && npm install frappe-gantt`
Expected: frappe-gantt added to dependencies in `package.json`.

- [ ] **Step 2: Verify installation**

Run: `cd frontend && node -e "require('frappe-gantt'); console.log('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add frappe-gantt dependency"
```

---

## Task 9: Create TaskTimeline component

**Files:**
- Create: `frontend/src/components/TaskTimeline.tsx`
- Create: `frontend/src/components/TaskTimeline.css`

- [ ] **Step 1: Create TaskTimeline.tsx**

Create `frontend/src/components/TaskTimeline.tsx` with the following content:

```tsx
import { useNavigate } from "react-router-dom";
import {
  TaskListItem,
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_COLORS,
} from "../types/tasks";
import "./TaskTimeline.css";

interface Props {
  tasks: TaskListItem[];
}

function formatShortDate(d: string) {
  return new Date(d).toLocaleDateString("zh-CN", {
    month: "numeric",
    day: "numeric",
  });
}

function daysBetween(a: string, b: string): number {
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(1, Math.round(ms / (1000 * 60 * 60 * 24)));
}

export default function TaskTimeline({ tasks }: Props) {
  const navigate = useNavigate();

  const sorted = [...tasks].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="timeline">
      {sorted.map((task) => {
        const color = STATUS_COLORS[task.status];
        const isActive = task.status === "in_progress" || task.status === "review";

        let durationText: string;
        if (task.status === "completed" && task.completed_at) {
          durationText = `创建: ${formatShortDate(task.created_at)} → 完成: ${formatShortDate(task.completed_at)} (${daysBetween(task.created_at, task.completed_at)} 天)`;
        } else if (isActive) {
          const days = daysBetween(task.created_at, new Date().toISOString());
          durationText = `创建: ${formatShortDate(task.created_at)} → 进行中 (已持续 ${days} 天)`;
        } else {
          durationText = `创建: ${formatShortDate(task.created_at)}`;
        }

        return (
          <div
            key={task.id}
            className="timeline-item"
            onClick={() => navigate(`/tasks/${task.id}`)}
          >
            <div className="timeline-dot-wrapper">
              <span
                className={`timeline-dot${isActive ? " pulse" : ""}`}
                style={{ backgroundColor: color }}
              />
            </div>
            <div className="timeline-card">
              <div className="timeline-card-header">
                <span
                  className="timeline-priority-dot"
                  style={{ backgroundColor: PRIORITY_COLORS[task.priority] }}
                />
                <span className="timeline-card-title">{task.title}</span>
                <span
                  className="task-status-badge"
                  style={{
                    backgroundColor: color + "18",
                    color: color,
                  }}
                >
                  {STATUS_LABELS[task.status]}
                </span>
              </div>
              <div className="timeline-card-meta">
                <span className="timeline-meta-text">
                  {task.assignee?.nickname || task.assignee?.username || "未分配"}
                </span>
                {task.tags.map((t) => (
                  <span
                    key={t.id}
                    className="task-tag"
                    style={{ backgroundColor: t.color + "18", color: t.color }}
                  >
                    {t.name}
                  </span>
                ))}
              </div>
              <div className="timeline-duration">{durationText}</div>
            </div>
          </div>
        );
      })}
      {sorted.length === 0 && (
        <div className="timeline-empty">暂无任务</div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create TaskTimeline.css**

Create `frontend/src/components/TaskTimeline.css` with the following content:

```css
.timeline {
  position: relative;
  padding-left: 28px;
}

.timeline::before {
  content: "";
  position: absolute;
  left: 11px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--border, #e5e8ec);
}

.timeline-item {
  position: relative;
  padding-bottom: 24px;
  cursor: pointer;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot-wrapper {
  position: absolute;
  left: -28px;
  top: 8px;
  width: 24px;
  display: flex;
  justify-content: center;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px var(--border, #e5e8ec);
  z-index: 1;
}

.timeline-dot.pulse {
  animation: timeline-pulse 2s ease-in-out infinite;
}

@keyframes timeline-pulse {
  0%, 100% { box-shadow: 0 0 0 2px var(--border, #e5e8ec); }
  50% { box-shadow: 0 0 0 4px var(--brand, #e85d4a); }
}

.timeline-card {
  background: #fff;
  border: 1px solid var(--border, #e5e8ec);
  border-radius: 10px;
  padding: 14px 18px;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.timeline-item:hover .timeline-card {
  box-shadow: 0 4px 12px rgba(26, 27, 46, 0.06);
  border-color: var(--brand, #e85d4a);
}

.timeline-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.timeline-priority-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.timeline-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text, #1a1b2e);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.timeline-meta-text {
  font-size: 12px;
  color: var(--text-sec, #6b7280);
}

.timeline-duration {
  font-size: 12px;
  color: var(--text-sec, #6b7280);
}

.timeline-empty {
  text-align: center;
  padding: 60px 0;
  color: var(--text-sec, #6b7280);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TaskTimeline.tsx frontend/src/components/TaskTimeline.css
git commit -m "feat: add TaskTimeline vertical timeline component"
```

---

## Task 10: Create TaskGantt component

**Files:**
- Create: `frontend/src/components/TaskGantt.tsx`
- Create: `frontend/src/components/TaskGantt.css`

- [ ] **Step 1: Create TaskGantt.tsx**

Create `frontend/src/components/TaskGantt.tsx` with the following content:

```tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Gantt from "frappe-gantt";
import { TaskListItem, STATUS_COLORS, STATUS_LABELS } from "../types/tasks";
import "frappe-gantt/dist/frappe-gantt.css";
import "./TaskGantt.css";

interface Props {
  tasks: TaskListItem[];
}

interface GanttTask {
  id: string;
  name: string;
  start: string;
  end: string;
  progress: number;
  dependencies: string;
  _status: string;
}

const STATUS_ORDER: Record<string, number> = {
  in_progress: 0,
  review: 1,
  pending: 2,
  completed: 3,
  cancelled: 4,
};

function statusToProgress(status: string): number {
  if (status === "completed") return 100;
  if (status === "in_progress" || status === "review") return 50;
  return 0;
}

function toDateStr(d: string): string {
  return d.split("T")[0];
}

export default function TaskGantt({ tasks }: Props) {
  const navigate = useNavigate();
  const svgRef = useRef<SVGSVGElement>(null);
  const ganttRef = useRef<Gantt | null>(null);
  const [viewMode, setViewMode] = useState<string>("Day");

  // Sort by status group, then by created_at within each group
  const sorted = [...tasks].sort((a, b) => {
    const sa = STATUS_ORDER[a.status] ?? 99;
    const sb = STATUS_ORDER[b.status] ?? 99;
    if (sa !== sb) return sa - sb;
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });

  const ganttTasks: GanttTask[] = sorted.map((task) => ({
    id: String(task.id),
    name: task.title,
    start: toDateStr(task.created_at),
    end: task.completed_at
      ? toDateStr(task.completed_at)
      : toDateStr(new Date().toISOString()),
    progress: statusToProgress(task.status),
    dependencies: "",
    _status: task.status,
  }));

  useEffect(() => {
    if (!svgRef.current || ganttTasks.length === 0) return;

    if (ganttRef.current) {
      // Update existing chart
      ganttRef.current.tasks = ganttTasks as any;
      ganttRef.current.refresh();
      ganttRef.current.change_view_mode(viewMode);
    } else {
      ganttRef.current = new Gantt(svgRef.current, ganttTasks as any, {
        view_mode: viewMode,
        readonly: true,
        popup: () => false,
        on_click: (task: any) => {
          const id = Number(task.id);
          if (id) navigate(`/tasks/${id}`);
        },
        custom_popup_html: null,
      });
    }

    // Apply status colors to bars
    applyBarColors(sorted);
  }, [ganttTasks.length, viewMode]);

  const applyBarColors = (taskList: TaskListItem[]) => {
    if (!svgRef.current) return;
    const bars = svgRef.current.querySelectorAll(".bar-wrapper");
    bars.forEach((bar, i) => {
      if (i < taskList.length) {
        const color = STATUS_COLORS[taskList[i].status];
        const barEl = bar.querySelector(".bar") as SVGElement;
        if (barEl) {
          barEl.setAttribute("fill", color);
          barEl.setAttribute("style", `fill: ${color};`);
        }
        const progressEl = bar.querySelector(".bar-progress") as SVGElement;
        if (progressEl) {
          progressEl.setAttribute("style", `fill: ${color}; opacity: 0.3;`);
        }
      }
    });
  };

  const handleViewModeChange = (mode: string) => {
    setViewMode(mode);
    if (ganttRef.current) {
      ganttRef.current.change_view_mode(mode);
      applyBarColors(sorted);
    }
  };

  if (tasks.length === 0) {
    return <div className="gantt-empty">暂无任务</div>;
  }

  return (
    <div className="gantt-wrapper">
      <div className="gantt-controls">
        {["Day", "Week", "Month"].map((mode) => (
          <button
            key={mode}
            className={`gantt-mode-btn${viewMode === mode ? " active" : ""}`}
            onClick={() => handleViewModeChange(mode)}
          >
            {{ Day: "日", Week: "周", Month: "月" }[mode]}
          </button>
        ))}
      </div>
      <div className="gantt-legend">
        {["in_progress", "review", "pending", "completed", "cancelled"].map((s) => (
          <span key={s} className="gantt-legend-item">
            <span
              className="gantt-legend-dot"
              style={{ backgroundColor: STATUS_COLORS[s as keyof typeof STATUS_COLORS] }}
            />
            {STATUS_LABELS[s as keyof typeof STATUS_LABELS]}
          </span>
        ))}
      </div>
      <svg ref={svgRef} className="gantt-svg" />
    </div>
  );
}
```

- [ ] **Step 2: Create TaskGantt.css**

Create `frontend/src/components/TaskGantt.css` with the following content:

```css
.gantt-wrapper {
  background: #fff;
  border: 1px solid var(--border, #e5e8ec);
  border-radius: 10px;
  overflow: hidden;
}

.gantt-controls {
  display: flex;
  gap: 4px;
  padding: 12px 16px 0;
}

.gantt-mode-btn {
  padding: 4px 14px;
  border: 1px solid var(--border, #e5e8ec);
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: var(--text-sec, #6b7280);
  transition: all 0.15s;
}

.gantt-mode-btn.active {
  background: var(--brand, #e85d4a);
  color: #fff;
  border-color: var(--brand, #e85d4a);
}

.gantt-mode-btn:hover:not(.active) {
  border-color: var(--brand, #e85d4a);
  color: var(--brand, #e85d4a);
}

.gantt-legend {
  display: flex;
  gap: 16px;
  padding: 8px 16px 12px;
  border-bottom: 1px solid var(--border, #e5e8ec);
  flex-wrap: wrap;
}

.gantt-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-sec, #6b7280);
}

.gantt-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

/* Override frappe-gantt default styles */
.gantt-svg {
  display: block;
  width: 100%;
}

.gantt-wrapper .gantt-container {
  font-family: system-ui, -apple-system, sans-serif;
}

.gantt-wrapper .grid-row {
  fill: #fff;
}

.gantt-wrapper .grid-row:nth-child(even) {
  fill: #fafafa;
}

.gantt-wrapper .grid-header {
  fill: var(--paper, #f7f7f4);
}

.gantt-wrapper .row-line {
  stroke: var(--border, #e5e8ec);
}

.gantt-wrapper .tick {
  stroke: var(--border, #e5e8ec);
}

.gantt-wrapper .tick-text {
  fill: var(--text-sec, #6b7280);
  font-size: 11px;
}

.gantt-wrapper .bar-label {
  fill: var(--text, #1a1b2e);
  font-size: 12px;
}

.gantt-wrapper .today-highlight {
  fill: var(--brand, #e85d4a);
  opacity: 0.08;
}

.gantt-wrapper .lower-text,
.gantt-wrapper .upper-text {
  fill: var(--text-sec, #6b7280);
}

.gantt-empty {
  text-align: center;
  padding: 60px 0;
  color: var(--text-sec, #6b7280);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TaskGantt.tsx frontend/src/components/TaskGantt.css
git commit -m "feat: add TaskGantt component with frappe-gantt"
```

---

## Task 11: Add view mode toggle to TaskListPage

**Files:**
- Modify: `frontend/src/pages/TaskListPage.tsx`
- Modify: `frontend/src/pages/TaskListPage.css`

- [ ] **Step 1: Add imports for new components**

At the top of `frontend/src/pages/TaskListPage.tsx`, add imports for the two new components:

```typescript
// Add after existing imports:
import TaskTimeline from "../components/TaskTimeline";
import TaskGantt from "../components/TaskGantt";
```

- [ ] **Step 2: Add viewMode state**

Add the `viewMode` state after the existing state declarations (after line 25):

```typescript
  const [viewMode, setViewMode] = useState<"list" | "timeline" | "gantt">("list");
```

- [ ] **Step 3: Add view toggle buttons to the header**

In the header section, after the "新建任务" button (around line 73), replace the entire header to include the view toggle:

```tsx
        {/* Header */}
        <div className="task-header">
          <button className="task-back" onClick={() => navigate("/")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
            </svg>
            返回
          </button>
          <h1 className="task-title">任务列表</h1>
          <div className="task-view-toggle">
            <button
              className={`task-view-btn${viewMode === "list" ? " active" : ""}`}
              onClick={() => setViewMode("list")}
              title="列表视图"
            >
              列表
            </button>
            <button
              className={`task-view-btn${viewMode === "timeline" ? " active" : ""}`}
              onClick={() => setViewMode("timeline")}
              title="时间线视图"
            >
              时间线
            </button>
            <button
              className={`task-view-btn${viewMode === "gantt" ? " active" : ""}`}
              onClick={() => setViewMode("gantt")}
              title="甘特图视图"
            >
              甘特图
            </button>
          </div>
          <button className="task-btn-primary" onClick={() => navigate("/tasks/new")}>
            + 新建任务
          </button>
        </div>
```

- [ ] **Step 4: Replace task list rendering with view mode switch**

Replace the task list rendering section (the entire block from `{tasks.length === 0 ?` through the closing of the task list) with view-mode-aware rendering:

```tsx
        {/* View Content */}
        {viewMode === "list" && (
          tasks.length === 0 ? (
            <div className="task-empty">
              <p>暂无任务</p>
              <button className="task-btn-primary" onClick={() => navigate("/tasks/new")}>创建第一个任务</button>
            </div>
          ) : (
            <div className="task-list">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="task-card"
                  onClick={() => navigate(`/tasks/${task.id}`)}
                >
                  <div className="task-card-left">
                    <span
                      className="task-priority-dot"
                      style={{ backgroundColor: PRIORITY_COLORS[task.priority] }}
                    />
                    <div className="task-card-info">
                      <div className="task-card-title">{task.title}</div>
                      <div className="task-card-meta">
                        <span
                          className="task-status-badge"
                          style={{
                            backgroundColor: STATUS_COLORS[task.status] + "18",
                            color: STATUS_COLORS[task.status],
                          }}
                        >
                          {STATUS_LABELS[task.status]}
                        </span>
                        {task.tags.map((t) => (
                          <span key={t.id} className="task-tag" style={{ backgroundColor: t.color + "18", color: t.color }}>
                            {t.name}
                          </span>
                        ))}
                        <span className="task-meta-text">
                          {task.assignee?.nickname || task.assignee?.username || "未分配"}
                        </span>
                        {task.attachment_count > 0 && <span className="task-meta-text">{task.attachment_count} 附件</span>}
                      </div>
                    </div>
                  </div>
                  <div className="task-card-right">
                    <span className="task-meta-text">{formatDate(task.created_at)}</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                      <path d="m9 18 6-6-6-6" />
                    </svg>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
        {viewMode === "timeline" && <TaskTimeline tasks={tasks} />}
        {viewMode === "gantt" && <TaskGantt tasks={tasks} />}
```

- [ ] **Step 5: Add view toggle styles to TaskListPage.css**

Append the following CSS to `frontend/src/pages/TaskListPage.css`:

```css
.task-view-toggle {
  display: flex;
  border: 1px solid var(--border, #e5e8ec);
  border-radius: 8px;
  overflow: hidden;
}

.task-view-btn {
  padding: 6px 14px;
  border: none;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: var(--text-sec, #6b7280);
  transition: all 0.15s;
  border-right: 1px solid var(--border, #e5e8ec);
}

.task-view-btn:last-child {
  border-right: none;
}

.task-view-btn.active {
  background: var(--brand, #e85d4a);
  color: #fff;
}

.task-view-btn:hover:not(.active) {
  background: var(--paper, #f7f7f4);
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/TaskListPage.tsx frontend/src/pages/TaskListPage.css
git commit -m "feat: add list/timeline/gantt view toggle to task list page"
```

---

## Task 12: Verify build and commit

- [ ] **Step 1: Run Django check**

Run: `uv run python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build completes with no errors.

- [ ] **Step 3: Start dev servers and visually verify**

Run: `uv run python manage.py runserver`
Run: `cd frontend && npm run dev`

Verify in browser:
1. Task list page loads with view toggle (列表 / 时间线 / 甘特图)
2. Click "时间线" → vertical timeline appears with tasks
3. Click "甘特图" → Gantt chart renders with task bars
4. Task form no longer shows date inputs
5. Task detail no longer shows start/due dates
6. Existing task list view still works correctly
