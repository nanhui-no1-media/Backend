import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { taskApi } from "../api/tasks";
import {
  TaskListItem,
  STATUS_LABELS, PRIORITY_LABELS,
  STATUS_BADGE_CLASS, PRIORITY_DOT_CLASS,
} from "../types/tasks";
import "../styles/list.css";
import TaskTimeline from "../components/TaskTimeline";
import TaskGantt from "../components/TaskGantt";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";
import { useLoginModal } from "../components/LoginModalProvider";

interface User {
  id: number;
  username: string;
  avatar: string | null;
  nickname: string;
}

export default function TaskListPage() {
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();
  const [user, setUser] = useState<User | null>(null);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [priorityFilter, setPriorityFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "timeline" | "gantt">("list");

  useEffect(() => {
    api.me()
      .then((d) => setUser({ ...d.user, avatar: d.profile.avatar, nickname: d.profile.nickname }))
      .catch(() => openLogin());
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

  if (loading) {
    return (
      <AppShell>
        <div className="container" style={{ padding: "var(--s-16) 0" }}>
          <p className="muted">加载中…</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>任务</span>
          </nav>
          <div className="page-head-row">
            <div>
              <h1>任务</h1>
              <p className="section-sub">社团拍摄、剪辑、文案与运营任务看板。</p>
            </div>
            <button className="btn btn-primary" onClick={() => navigate("/tasks/new")}>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
              新建任务
            </button>
          </div>
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        {/* 工具条：搜索 + 优先级 + 视图切换 */}
        <div className="task-toolbar">
          <div className="input-affix search-affix">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
            <input className="input" type="search" placeholder="搜索任务…" aria-label="搜索任务" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <select className="select" aria-label="优先级" value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
            <option value="">全部优先级</option>
            {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <div className="spacer" />
          <div className="seg" role="tablist" aria-label="视图">
            {(["list", "timeline", "gantt"] as const).map((m) => (
              <button key={m} className="seg-btn" type="button" aria-selected={viewMode === m} onClick={() => setViewMode(m)}>
                {m === "list" ? "列表" : m === "timeline" ? "时间线" : "甘特图"}
              </button>
            ))}
          </div>
        </div>

        {/* 状态筛选 chip 行 */}
        <div className="filter-bar" role="tablist" aria-label="任务状态">
          <button className="chip" aria-pressed={statusFilter === ""} onClick={() => setStatusFilter("")}>全部</button>
          {Object.entries(STATUS_LABELS).map(([k, v]) => (
            <button key={k} className="chip" aria-pressed={statusFilter === k} onClick={() => setStatusFilter(k)}>{v}</button>
          ))}
        </div>

        {/* 视图内容 */}
        {viewMode === "list" && (
          tasks.length === 0 ? (
            <div className="task-empty">
              <p>暂无任务</p>
              <button className="btn btn-primary" onClick={() => navigate("/tasks/new")}>创建第一个任务</button>
            </div>
          ) : (
            tasks.map((task) => (
              <a key={task.id} className="task-card" href="#" onClick={(e) => { e.preventDefault(); navigate(`/tasks/${task.id}`); }}>
                <div className="tc-left">
                  <span className={"prio-dot " + PRIORITY_DOT_CLASS[task.priority]} title={"优先级：" + (PRIORITY_LABELS[task.priority] || "")} />
                  <div className="tc-info">
                    <div className="tc-title">{task.title}</div>
                    <div className="tc-meta">
                      <span className={"badge " + STATUS_BADGE_CLASS[task.status]}>{STATUS_LABELS[task.status]}</span>
                      {task.reject_reason && <span className="badge badge-warning">被打回</span>}
                      {task.tags.map((t) => (
                        <span key={t.id} className="tag-mini">{t.name}</span>
                      ))}
                      <span className="who">
                        {task.assignee && <Avatar user={task.assignee} />}
                        {task.assignee?.nickname || task.assignee?.username || "未分配"}
                      </span>
                      {task.attachment_count > 0 && <span>{task.attachment_count} 附件</span>}
                    </div>
                  </div>
                </div>
                <div className="tc-right">
                  <span className="date">{formatDate(task.created_at)}</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
                </div>
              </a>
            ))
          )
        )}
        {viewMode === "timeline" && <TaskTimeline tasks={tasks} />}
        {viewMode === "gantt" && <TaskGantt tasks={tasks} />}
      </div>
    </AppShell>
  );
}
