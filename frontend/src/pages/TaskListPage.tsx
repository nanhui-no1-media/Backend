import { useState, useEffect, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { taskApi } from "../api/tasks";
import {
  TaskListItem, TaskStatus, TaskPriority,
  STATUS_LABELS, PRIORITY_LABELS, PRIORITY_COLORS, STATUS_COLORS,
} from "../types/tasks";
import "./TaskListPage.css";

interface User {
  id: number;
  username: string;
  avatar: string | null;
  nickname: string;
}

export default function TaskListPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [priorityFilter, setPriorityFilter] = useState<string>("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.me()
      .then((d) => setUser({ ...d.user, avatar: d.profile.avatar, nickname: d.profile.nickname }))
      .catch(() => navigate("/login"));
  }, [navigate]);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (priorityFilter) params.priority = priorityFilter;
    if (search) params.search = search;

    taskApi.list(params)
      .then((data) => setTasks(data.results || data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [statusFilter, priorityFilter, search]);

  const formatDate = (d: string | null) => {
    if (!d) return "-";
    return new Date(d).toLocaleDateString("zh-CN");
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  };

  if (loading) {
    return <div className="task-page"><div className="task-loading">加载中...</div></div>;
  }

  return (
    <div className="task-page">
      <div className="task-container">
        {/* Header */}
        <div className="task-header">
          <button className="task-back" onClick={() => navigate("/")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
            </svg>
            返回
          </button>
          <h1 className="task-title">任务列表</h1>
          <button className="task-btn-primary" onClick={() => navigate("/tasks/new")}>
            + 新建任务
          </button>
        </div>

        {/* Filters */}
        <div className="task-filters">
          <input
            type="text"
            className="task-search"
            placeholder="搜索任务..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="task-select">
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} className="task-select">
            <option value="">全部优先级</option>
            {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>

        {/* Task List */}
        {tasks.length === 0 ? (
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
                      <span className="task-meta-text">{formatDate(task.due_date)}</span>
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
        )}
      </div>
    </div>
  );
}
