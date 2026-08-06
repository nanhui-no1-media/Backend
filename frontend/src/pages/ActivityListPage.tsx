import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { activityApi } from "../api/activities";
import {
  ActivityListItem,
  ActivityType,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_BADGE_CLASS,
} from "../types/activities";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";
import "../styles/list.css";

function formatCountdown(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "即将开始";
  const h = Math.floor(ms / 3600000);
  if (h < 24) return `${h} 小时`;
  return `${Math.floor(h / 24)} 天`;
}

export default function ActivityListPage() {
  const navigate = useNavigate();
  const [activities, setActivities] = useState<ActivityListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<ActivityType | "">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    const params: Record<string, string> = {};
    if (typeFilter) params.type = typeFilter;
    if (search) params.search = search;
    activityApi
      .list(params)
      .then((data) => setActivities(data.results || []))
      .catch((err) => {
        setError(err.message);
        setActivities([]);
      })
      .finally(() => setLoading(false));
  }, [typeFilter, search]);

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>活动</span>
          </nav>
          <div className="page-head-row">
            <div>
              <h1>活动</h1>
              <p className="section-sub">众议（投票）与征集（收作品），发起即对全体已验证成员开放。</p>
            </div>
            <button className="btn btn-primary" onClick={() => navigate("/activity/new")}>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
              发起活动
            </button>
          </div>
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        {error && (
          <div className="alert alert-danger" style={{ margin: "var(--s-6) 0 var(--s-4)" }}>
            <span>{error}</span>
          </div>
        )}

        <div className="prop-tabs">
          <div className="seg" role="tablist" aria-label="活动类型">
            <button className="seg-btn" type="button" aria-selected={typeFilter === ""} onClick={() => setTypeFilter("")}>全部</button>
            <button className="seg-btn" type="button" aria-selected={typeFilter === "deliberation"} onClick={() => setTypeFilter("deliberation")}>众议</button>
            <button className="seg-btn" type="button" aria-selected={typeFilter === "collection"} onClick={() => setTypeFilter("collection")}>征集</button>
          </div>
        </div>

        <div className="prop-filter">
          <div className="input-affix search-affix">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
            <input className="input" type="search" placeholder="搜索活动…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>

        {loading ? (
          <p className="muted" style={{ padding: "var(--s-8) 0" }}>加载中…</p>
        ) : activities.length === 0 ? (
          <div className="prop-empty">
            <p>暂无活动</p>
            <button className="btn btn-primary" onClick={() => navigate("/activity/new")}>发起第一个活动</button>
          </div>
        ) : (
          activities.map((a) => (
            <a key={a.id} className="prop-card" href="#" onClick={(e) => { e.preventDefault(); navigate(`/activity/${a.id}`); }}>
              <div className="pc-title">{a.title}</div>
              <div className="pc-meta">
                <span className={"badge " + ACTIVITY_STATUS_BADGE_CLASS[a.status]}>{ACTIVITY_STATUS_LABELS[a.status]}</span>
                <span className="type-tag">{ACTIVITY_TYPE_LABELS[a.type]}</span>
                {a.creator && (
                  <span className="who">
                    <Avatar user={a.creator} />
                    {a.creator.nickname || a.creator.username}
                  </span>
                )}
                {a.status === "scheduled" && a.start_at ? (
                  <span>⏱ 距开始 {formatCountdown(a.start_at)}</span>
                ) : a.end_at ? (
                  <span>截止 {new Date(a.end_at).toLocaleDateString("zh-CN")}</span>
                ) : null}
                <span className="tnum">{new Date(a.created_at).toLocaleDateString("zh-CN")}</span>
              </div>
            </a>
          ))
        )}
      </div>
    </AppShell>
  );
}
