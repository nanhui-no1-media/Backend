import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import Pagination from "../components/Pagination";
import { usePagedList } from "../hooks/usePagedList";
import { reviewsApi } from "../api/reviews";
import {
  type ReviewItem,
  type ReviewStatus,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_BADGE,
  TARGET_TYPE_LABELS,
} from "../types/reviews";
import "../styles/list.css";
import "../styles/form.css";

const PAGE_SIZE = 20;
const TARGET_PATH: Record<string, string> = {
  news: "/news",
  activity: "/activity",
};

export default function ReviewQueuePage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ReviewStatus | "">("pending");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectId, setRejectId] = useState<number | null>(null);
  const [rejectComment, setRejectComment] = useState("");
  const [error, setError] = useState("");

  const { data, page, setPage, totalPages, loading, refetch, error: loadError } = usePagedList<ReviewItem>(
    (params) => reviewsApi.list(params),
    PAGE_SIZE,
    status ? { status } : {},
  );

  const run = async (id: number, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError("");
    try {
      await fn();
      setRejectId(null);
      setRejectComment("");
      refetch();
    } catch (e: any) {
      setError(e.message || "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const goTarget = (row: ReviewItem) => {
    const base = TARGET_PATH[row.target_type || ""];
    if (base && row.target_id) navigate(`${base}/${row.target_id}`);
  };

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>审核队列</span>
          </nav>
          <div className="page-head-row">
            <div>
              <h1>审核队列</h1>
              <p className="section-sub">新闻 / 活动 / 教程共用一条审核轴。通过后才对公众公开。</p>
            </div>
          </div>
        </div>
      </div>

      <div className="container">
        <div className="filter-bar" role="tablist" aria-label="审核状态">
          <button className="chip" aria-pressed={status === "pending"} onClick={() => setStatus("pending")}>待审</button>
          <button className="chip" aria-pressed={status === "approved"} onClick={() => setStatus("approved")}>已通过</button>
          <button className="chip" aria-pressed={status === "rejected"} onClick={() => setStatus("rejected")}>已驳回</button>
          <button className="chip" aria-pressed={status === "removed"} onClick={() => setStatus("removed")}>已下架</button>
          <button className="chip" aria-pressed={status === ""} onClick={() => setStatus("")}>全部</button>
        </div>

        {(error || loadError) && <div className="alert alert-warning" style={{ marginBottom: 12 }}>{error || loadError}</div>}

        {loading ? (
          <p className="task-empty">加载中…</p>
        ) : loadError ? null : data.length === 0 ? (
          <p className="task-empty">该状态下暂无审核项。</p>
        ) : data.map((row) => (
          <div key={row.id} className="task-card" style={{ cursor: "default" }}>
            <div className="tc-left">
              <div className="tc-info">
                <div className="tc-title">
                  <a href="#" onClick={(e) => { e.preventDefault(); goTarget(row); }}>{row.title}</a>
                </div>
                <div className="tc-meta">
                  <span className="badge badge-ghost">{TARGET_TYPE_LABELS[row.target_type || ""] || row.target_type}</span>
                  <span className={"badge " + REVIEW_STATUS_BADGE[row.status]}>{REVIEW_STATUS_LABELS[row.status]}</span>
                  {row.comment && <span>评语：{row.comment}</span>}
                </div>
              </div>
            </div>
            <div className="tc-right">
              {row.status === "pending" && (
                <>
                  <button className="btn btn-success btn-sm" disabled={busyId === row.id}
                          onClick={() => run(row.id, () => reviewsApi.approve(row.id))}>通过</button>
                  <button className="btn btn-ghost btn-sm" disabled={busyId === row.id}
                          onClick={() => { setRejectId(row.id); setRejectComment(""); }}>驳回</button>
                </>
              )}
              {row.status === "approved" && (
                <button className="btn btn-ghost btn-sm" disabled={busyId === row.id}
                        onClick={() => run(row.id, () => reviewsApi.remove(row.id))}>下架</button>
              )}
            </div>
            {rejectId === row.id && (
              <div style={{ flexBasis: "100%", paddingTop: 8 }}>
                <textarea className="input" rows={2} placeholder="驳回评语（必填）"
                          value={rejectComment} onChange={(e) => setRejectComment(e.target.value)} />
                <div className="form-actions" style={{ marginTop: 8 }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => setRejectId(null)}>取消</button>
                  <button className="btn btn-primary btn-sm" disabled={!rejectComment.trim() || busyId === row.id}
                          onClick={() => run(row.id, () => reviewsApi.reject(row.id, rejectComment.trim()))}>确认驳回</button>
                </div>
              </div>
            )}
          </div>
        ))}

        {!loading && <Pagination page={page} totalPages={totalPages} onChange={setPage} />}
      </div>
    </AppShell>
  );
}
