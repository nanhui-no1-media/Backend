import { useNavigate } from "react-router-dom";
import {
  TaskListItem,
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_COLORS,
} from "../types/tasks";
import "./TaskTimeline.css";
import Avatar from "./Avatar";

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
                <span className="timeline-meta-text user-with-avatar">
                  {task.assignee && <Avatar user={task.assignee} />}
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
