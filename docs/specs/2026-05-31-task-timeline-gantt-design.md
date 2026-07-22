# Task Timeline & Gantt Chart Design

**Date**: 2026-05-31
**Status**: Approved

## Overview

Remove manual `start_date` and `due_date` fields from the task system, keep automatic `created_at` and `completed_at` as the sole time fields. Add Timeline and Gantt Chart view modes to the task list page.

## Backend Changes

### Model (`tasks/models.py`)

- **Remove** `start_date` (DateField) and `due_date` (DateField)
- **Keep** `created_at` (auto_now_add) and `completed_at` (set on completion)

### Serializer (`tasks/serializers.py`)

- `TaskListSerializer.fields`: remove `start_date`, `due_date`
- `TaskDetailSerializer.fields`: remove `start_date`, `due_date`
- `TaskDetailSerializer.read_only_fields`: no change needed (`completed_at` already read-only)

### Views (`tasks/views.py`)

- `ordering_fields`: remove `due_date`, add `completed_at`

### Migration

- Generate migration to drop the two columns from the database

## Frontend Data Layer Changes

### Types (`frontend/src/types/tasks.ts`)

- `TaskListItem`: remove `start_date`, `due_date`
- `TaskDetail`: remove `start_date`, `due_date`
- `TaskFormData`: remove `start_date`, `due_date`

### Form Page (`frontend/src/pages/TaskFormPage.tsx`)

- Remove `startDate` and `dueDate` state variables
- Remove the date picker form row (two `<input type="date">`)
- Remove field assignments in `handleSubmit`
- Remove field population in edit-mode `useEffect`

### Detail Page (`frontend/src/pages/TaskDetailPage.tsx`)

- Remove "开始日期" and "截止日期" `meta-item` entries from the metadata grid
- Keep "创建时间" display as-is

### List Page (`frontend/src/pages/TaskListPage.tsx`)

- Remove `formatDate(task.due_date)` from task card

## Timeline View

### Component: `frontend/src/components/TaskTimeline.tsx`

**Props**: `tasks: TaskListItem[]`

**Layout**: Vertical timeline with a left-side line, colored dots per status, and right-side cards.

```
  ● 任务A [已完成]        ← green dot
  │  Title, assignee, tags
  │  创建: 5/1 → 完成: 5/15 (耗时 14 天)
  │
  ● 任务B [进行中]        ← blue dot, pulse animation
  │  Title, assignee, tags
  │  创建: 5/10 → 进行中 (已持续 20 天)
  │
  ● 任务C [待处理]        ← gray dot
     Title, assignee, tags
     创建: 5/20
```

**Sorting**: By `created_at` descending (newest first)

**Interactions**:
- Click task node → navigate to `/tasks/{id}`
- Dot color follows `STATUS_COLORS`

**Implementation**: Pure CSS — left vertical line via `::before`, absolute-positioned dots, right-side card layout

**Duration display**:
- Completed: "创建: X → 完成: Y (耗时 N 天)"
- In progress/review: "创建: X → 进行中 (已持续 N 天)"
- Pending/cancelled: "创建: X"

## Gantt Chart View

### Dependency: `frappe-gantt` (MIT, ~15KB)

Install via npm. frappe-gantt depends on SVG.js which it bundles.

### Component: `frontend/src/components/TaskGantt.tsx`

**Props**: `tasks: TaskListItem[]`

**Data transformation** to frappe-gantt format:

```typescript
{
  id: string(task.id),
  name: task.title,
  start: task.created_at.split('T')[0],       // date portion
  end: task.completed_at
    ? task.completed_at.split('T')[0]
    : new Date().toISOString().split('T')[0],   // today if not completed
  progress: statusToProgress(task.status),      // completed=100, in_progress=50, else=0
  dependencies: ''
}
```

**Grouping**: Sort tasks by status order (in_progress → review → pending → completed → cancelled) so same-status tasks are adjacent. No explicit group headers — visual proximity + status colors convey grouping.

**Time axis modes**: Day (default) / Week / Month, with toggle buttons (frappe-gantt native feature)

**Interactions**:
- Click task bar → navigate to `/tasks/{id}` (via frappe-gantt `on_click` callback)
- Horizontal scroll/pan native to frappe-gantt

**Style override** (`frontend/src/components/TaskGantt.css`):
- Override frappe-gantt default styles using project CSS variables (`--brand`, `--text`, `--border`, `--paper`)
- Task bar colors follow `STATUS_COLORS`
- Font family matches project system font stack

## List Page View Switching

### TaskListPage modification

Add a view mode toggle button group to the right of the existing filter bar:

```
[搜索框]  [状态筛选]  [优先级筛选]     [列表] [时间线] [甘特图]
```

**State**: `viewMode: "list" | "timeline" | "gantt"` (default: `"list"`)

**Rendering logic**:
- `"list"` → existing task card list (unchanged)
- `"timeline"` → `<TaskTimeline tasks={tasks} />`
- `"gantt"` → `<TaskGantt tasks={tasks} />`

**Data reuse**: All three views share the same `tasks` state and filter conditions. No additional API calls on view switch.

**Layout**: The selected view replaces the task list area. Filter bar remains visible across all modes.

## Files Modified

| File | Change |
|------|--------|
| `tasks/models.py` | Remove `start_date`, `due_date` |
| `tasks/serializers.py` | Remove fields from both serializers |
| `tasks/views.py` | Update `ordering_fields` |
| New migration | Drop database columns |
| `frontend/src/types/tasks.ts` | Remove fields from interfaces |
| `frontend/src/pages/TaskFormPage.tsx` | Remove date inputs |
| `frontend/src/pages/TaskDetailPage.tsx` | Remove date display |
| `frontend/src/pages/TaskListPage.tsx` | Remove due date + add view toggle |
| `frontend/src/components/TaskTimeline.tsx` | **New**: vertical timeline |
| `frontend/src/components/TaskGantt.tsx` | **New**: Gantt chart wrapper |
| `frontend/src/components/TaskGantt.css` | **New**: style overrides |

## Implementation Order

1. Backend: model changes → serializer → views → migration
2. Frontend data layer: types → form → detail → list (remove date fields)
3. Frontend new components: TaskTimeline → TaskGantt
4. Frontend integration: view toggle on TaskListPage
5. Style polish and testing
