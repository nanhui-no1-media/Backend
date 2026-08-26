import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { proposalApi } from "../api/proposals";
import { attachmentApi } from "../api/attachments";
import {
  ProposalListItem,
  FeedbackCategory,
  FeedbackFormData,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_BADGE_CLASS,
  FEEDBACK_CATEGORY_LABELS,
} from "../types/proposals";
import Pagination from "../components/Pagination";
import AppShell from "../components/AppShell";
import { usePagedList } from "../hooks/usePagedList";
import type { Paginated } from "../types/pagination";
import "../styles/list.css";

const PAGE_SIZE = 20;

interface CurrentUser {
  id: number;
  username: string;
  can_view_feedback?: boolean;
}

export default function ProposalListPage() {
  const navigate = useNavigate();
  // undefined = 解析中, null = 未登录（匿名）
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  // 反馈表单（公开匿名提交）
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [fbTitle, setFbTitle] = useState("");
  const [fbCategory, setFbCategory] = useState<FeedbackCategory>("suggestion");
  const [fbDesc, setFbDesc] = useState("");
  const [fbContact, setFbContact] = useState("");
  const [fbSubmitting, setFbSubmitting] = useState(false);
  const [fbSuccess, setFbSuccess] = useState(false);
  // 署名反馈（登录用户）：记录身份、可附图片/视频证据
  const [fbAttributed, setFbAttributed] = useState(false);
  const [fbFiles, setFbFiles] = useState<File[]>([]);
  const [fbUploading, setFbUploading] = useState(false);
  const [fbUploadProgress, setFbUploadProgress] = useState<number | null>(null);

  useEffect(() => {
    api.me()
      .then((d) => setUser({ id: d.user.id, username: d.user.username, can_view_feedback: d.user.permissions?.can_view_feedback }))
      .catch(() => setUser(null));
  }, []);

  const canViewFeedback = !!user?.can_view_feedback;
  const isLoggedIn = !!user;

  // 无审批权限时页面只剩提交表单，默认展开；有权限者保持收起，先看列表。
  useEffect(() => {
    if (user === undefined) return;
    if (!user?.can_view_feedback) setShowFeedbackForm(true);
  }, [user]);

  // 审批列表：仅持 view_feedback 者可见；无权限只保留提交表单。
  const {
    data: proposals,
    page,
    setPage,
    totalPages,
    loading,
    error: listError,
    refetch,
  } = usePagedList<ProposalListItem>(
    (params) => proposalApi.list(params) as Promise<Paginated<ProposalListItem>>,
    PAGE_SIZE,
    { status: statusFilter || undefined, search: search || undefined },
    canViewFeedback,
  );

  const submitFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fbTitle.trim() || !fbDesc.trim()) {
      setError("标题和内容不能为空");
      return;
    }
    setFbSubmitting(true);
    setError("");
    const data: FeedbackFormData = {
      title: fbTitle.trim(),
      description: fbDesc.trim(),
      feedback_category: fbCategory,
    };
    if (fbContact.trim()) data.contact = fbContact.trim();
    if (fbAttributed) data.disclose_identity = true;
    try {
      const created = await proposalApi.submitFeedback(data);
      // 署名反馈：按返回的 id 挂附件（按大小自动选路：≤50MB 同步、>50MB tus 可续传）
      if (fbAttributed && fbFiles.length) {
        setFbUploading(true);
        for (const f of fbFiles) {
          await attachmentApi.uploadRouted({
            parentType: "proposal",
            parentId: created.id,
            file: f,
            onProgress: setFbUploadProgress,
          });
        }
      }
      setFbSuccess(true);
      setFbTitle("");
      setFbDesc("");
      setFbContact("");
      setFbCategory("suggestion");
      setFbAttributed(false);
      setFbFiles([]);
      refetch();
      setTimeout(() => setFbSuccess(false), 5000);
    } catch (err: any) {
      setError(err.status === 429
        ? "今日提交次数已达上限（10 条），请明天再试。"
        : err.message);
    } finally {
      setFbSubmitting(false);
      setFbUploading(false);
      setFbUploadProgress(null);
    }
  };

  const renderCard = (p: ProposalListItem) => (
    <a key={p.id} className="prop-card" href="#" onClick={(e) => { e.preventDefault(); navigate(`/feedback/${p.id}`); }}>
      <div className="pc-title">{p.title}</div>
      <div className="pc-meta">
        <span className={"badge " + PROPOSAL_STATUS_BADGE_CLASS[p.status]}>{PROPOSAL_STATUS_LABELS[p.status]}</span>
        <span className="type-tag fb">
          {FEEDBACK_CATEGORY_LABELS[p.feedback_category as FeedbackCategory] || "意见反馈"}
        </span>
        {p.attachment_count > 0 && <span>{p.attachment_count} 附件</span>}
        <span className="tnum">{new Date(p.created_at).toLocaleDateString("zh-CN")}</span>
      </div>
      {p.status === "rejected" && p.reject_reason && (
        <div className="pc-reason"><b>拒绝理由：</b>{p.reject_reason}</div>
      )}
    </a>
  );

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>意见反馈</span>
          </nav>
          <h1>意见反馈</h1>
          <p className="section-sub">匿名或署名提交建议 / 投诉 / 举报。</p>
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        {(error || listError) && (
          <div className="alert alert-danger" style={{ margin: "var(--s-6) 0 var(--s-4)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
            <span>{error || listError}</span>
          </div>
        )}

        {/* 公开匿名反馈表单：所有人均可提交 */}
        <section className={"fb-section" + (showFeedbackForm ? " is-open" : "")}>
          <button className="fb-head" type="button" aria-expanded={showFeedbackForm} onClick={() => setShowFeedbackForm((v) => !v)}>
            <div>
              <div className="fb-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M4 5h16v12H7l-3 3z" /></svg>
                提交意见反馈 / 举报
              </div>
              <div className="fb-hint">可匿名或署名（登录后）提交。</div>
            </div>
            <span className="fb-toggle">{showFeedbackForm ? "收起" : "展开"}
              <svg className="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
            </span>
          </button>

          {showFeedbackForm && (
            <div className="fb-body">
              {fbSuccess && (
                <div className="alert alert-success fb-done">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
                  <span>已提交，感谢你的反馈！</span>
                </div>
              )}
              <form onSubmit={submitFeedback}>
                <div className="form-grid">
                  <div className="field">
                    <label className="label">类别</label>
                    <select className="select" value={fbCategory} onChange={(e) => setFbCategory(e.target.value as FeedbackCategory)}>
                      {(Object.keys(FEEDBACK_CATEGORY_LABELS) as FeedbackCategory[]).map((k) => (
                        <option key={k} value={k}>{FEEDBACK_CATEGORY_LABELS[k]}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label className="label">联系方式 <span className="hint">（选填）</span></label>
                    <input className="input" type="text" value={fbContact} onChange={(e) => setFbContact(e.target.value)} placeholder="如需回复请留下联系方式" maxLength={100} />
                  </div>
                </div>
                <div className="field">
                  <label className="label">标题 <span className="hint">*</span></label>
                  <input className="input" type="text" value={fbTitle} onChange={(e) => setFbTitle(e.target.value)} placeholder="一句话概括" maxLength={200} required />
                </div>
                <div className="field">
                  <label className="label">详细内容 <span className="hint">*</span></label>
                  <textarea className="textarea" value={fbDesc} onChange={(e) => setFbDesc(e.target.value)} placeholder="详细描述你的建议 / 投诉 / 举报内容…" rows={4} required />
                </div>
                {isLoggedIn && (
                  <div className="field">
                    <label className="label">署名 <span className="hint">（登录用户）</span></label>
                    <label className="fb-attrib">
                      <input type="checkbox" checked={fbAttributed} onChange={(e) => { setFbAttributed(e.target.checked); if (!e.target.checked) setFbFiles([]); }} />
                      <span>署名提交 —— 处理人可见我的身份，可附带图片 / 视频证据</span>
                    </label>
                    {fbAttributed && (
                      <input type="file" multiple accept="image/*,video/*" onChange={(e) => setFbFiles(Array.from(e.target.files || []))} />
                    )}
                  </div>
                )}
                <div><button className="btn btn-primary" type="submit" disabled={fbSubmitting || fbUploading}>{fbUploading ? "上传附件中…" : fbSubmitting ? "提交中…" : fbAttributed ? "署名提交" : "匿名提交"}</button></div>
                {fbUploadProgress != null && (
                  <div style={{ height: 6, background: "#e5e7eb", borderRadius: 4, overflow: "hidden", margin: "8px 0 0" }} aria-label="上传进度">
                    <div style={{ width: `${Math.round(fbUploadProgress * 100)}%`, height: "100%", background: "#2563eb", transition: "width .2s" }} />
                  </div>
                )}
              </form>
            </div>
          )}
        </section>

        {canViewFeedback && (
          <>
            <div className="prop-filter">
              <div className="input-affix search-affix">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
                <input className="input" type="search" placeholder="搜索反馈…" value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
            </div>

            <div className="filter-bar" role="tablist" aria-label="反馈状态" style={{ paddingTop: 0 }}>
              <button className="chip" aria-pressed={statusFilter === ""} onClick={() => setStatusFilter("")}>全部</button>
              {(Object.keys(PROPOSAL_STATUS_LABELS) as (keyof typeof PROPOSAL_STATUS_LABELS)[]).map((k) => (
                <button key={k} className="chip" aria-pressed={statusFilter === k} onClick={() => setStatusFilter(k)}>{PROPOSAL_STATUS_LABELS[k]}</button>
              ))}
            </div>

            {loading ? (
              <p className="muted" style={{ padding: "var(--s-8) 0" }}>加载中…</p>
            ) : proposals.length === 0 ? (
              <div className="prop-empty">
                <p>暂无反馈</p>
              </div>
            ) : (
              proposals.map(renderCard)
            )}
            {!loading && proposals.length > 0 && (
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
