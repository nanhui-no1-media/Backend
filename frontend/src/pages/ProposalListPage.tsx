import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { proposalApi } from "../api/proposals";
import {
  ProposalListItem,
  ProposalType,
  FeedbackCategory,
  FeedbackFormData,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_BADGE_CLASS,
  ACTIVITY_TYPE_LABELS,
  FEEDBACK_CATEGORY_LABELS,
} from "../types/proposals";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";
import { useLoginModal } from "../components/LoginModalProvider";
import "../styles/list.css";

interface CurrentUser {
  id: number;
  username: string;
  is_president?: boolean;
}

export default function ProposalListPage() {
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();
  // undefined = 解析中, null = 未登录（匿名）
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);
  const [proposals, setProposals] = useState<ProposalListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [typeFilter, setTypeFilter] = useState<ProposalType>("activity");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // 反馈表单（公开匿名提交）
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [fbTitle, setFbTitle] = useState("");
  const [fbCategory, setFbCategory] = useState<FeedbackCategory>("suggestion");
  const [fbDesc, setFbDesc] = useState("");
  const [fbContact, setFbContact] = useState("");
  const [fbSubmitting, setFbSubmitting] = useState(false);
  const [fbSuccess, setFbSuccess] = useState(false);

  useEffect(() => {
    api.me()
      .then((d) => setUser({ id: d.user.id, username: d.user.username, is_president: d.user.is_president }))
      .catch(() => setUser(null));
  }, []);

  const isPresident = !!user?.is_president;
  const isLoggedIn = !!user;

  // 非社长不可看反馈 tab，自动回到活动
  useEffect(() => {
    if (isLoggedIn && !isPresident && typeFilter === "feedback") {
      setTypeFilter("activity");
    }
  }, [isLoggedIn, isPresident, typeFilter]);

  // 匿名用户默认展开反馈表单
  useEffect(() => {
    if (user === null) setShowFeedbackForm(true);
  }, [user]);

  // 加载列表（仅登录用户）
  useEffect(() => {
    if (user === undefined || user === null) return;
    setLoading(true);
    setError("");
    const params: Record<string, string> = { proposal_type: typeFilter };
    if (statusFilter) params.status = statusFilter;
    if (search) params.search = search;
    proposalApi.list(params)
      .then((data: any) => setProposals(data.results || data))
      .catch((err) => { setError(err.message); setProposals([]); })
      .finally(() => setLoading(false));
  }, [user, typeFilter, statusFilter, search, reloadKey]);

  const submitFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fbTitle.trim() || !fbDesc.trim()) {
      setError("标题和内容不能为空");
      return;
    }
    setFbSubmitting(true);
    setError("");
    const data: FeedbackFormData = {
      proposal_type: "feedback",
      title: fbTitle.trim(),
      description: fbDesc.trim(),
      feedback_category: fbCategory,
    };
    if (fbContact.trim()) data.contact = fbContact.trim();
    try {
      await proposalApi.submitFeedback(data);
      setFbSuccess(true);
      setFbTitle("");
      setFbDesc("");
      setFbContact("");
      setFbCategory("suggestion");
      if (isPresident && typeFilter === "feedback") setReloadKey((k) => k + 1);
      setTimeout(() => setFbSuccess(false), 5000);
    } catch (err: any) {
      setError(err.status === 429
        ? "今日提交次数已达上限（10 条），请明天再试。"
        : err.message);
    } finally {
      setFbSubmitting(false);
    }
  };

  const formatRemaining = (endAt: string | null) => {
    if (!endAt) return "";
    const ms = new Date(endAt).getTime() - Date.now();
    if (ms <= 0) return "已截止";
    const h = Math.floor(ms / 3600000);
    if (h < 24) return `剩余 ${h} 小时`;
    return `剩余 ${Math.floor(h / 24)} 天`;
  };

  const renderCard = (p: ProposalListItem) => {
    const isActivity = p.proposal_type === "activity";
    const total = p.vote_summary ? (p.vote_summary.approve + p.vote_summary.oppose + p.vote_summary.abstain) : 0;
    const pct = (n: number) => (total > 0 ? Math.round((n / total) * 100) : 0);
    return (
      <a key={p.id} className="prop-card" href="#" onClick={(e) => { e.preventDefault(); navigate(`/activity/${p.id}`); }}>
        <div className="pc-title">{p.title}</div>
        <div className="pc-meta">
          <span className={"badge " + PROPOSAL_STATUS_BADGE_CLASS[p.status]}>{PROPOSAL_STATUS_LABELS[p.status]}</span>
          <span className={"type-tag" + (isActivity ? "" : " fb")}>
            {isActivity
              ? ACTIVITY_TYPE_LABELS[p.activity_type as keyof typeof ACTIVITY_TYPE_LABELS] || "活动申报"
              : FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "意见反馈"}
          </span>
          <span className="who">
            {isActivity && p.creator ? (
              <>
                <Avatar user={p.creator} />
                {p.creator.nickname || p.creator.username}
              </>
            ) : isActivity ? (
              "（未知）"
            ) : (
              "匿名"
            )}
          </span>
          {isActivity && p.vote_summary && (
            <span className="vote">
              <span className="votebar">
                <i className="app" style={{ width: pct(p.vote_summary.approve) + "%" }} />
                <i className="opp" style={{ width: pct(p.vote_summary.oppose) + "%" }} />
                <i className="abs" style={{ width: pct(p.vote_summary.abstain) + "%" }} />
              </span>
              <span className="vote-num">
                <span className="app">赞成 {p.vote_summary.approve}</span>
                <span className="opp">反对 {p.vote_summary.oppose}</span>
                <span className="abs">弃权 {p.vote_summary.abstain}</span>
              </span>
            </span>
          )}
          {isActivity && p.status === "voting" && (
            <span className="remain">⏱ {formatRemaining(p.voting_end_at)}</span>
          )}
          {p.attachment_count > 0 && <span>{p.attachment_count} 附件</span>}
          <span className="tnum">{new Date(p.created_at).toLocaleDateString("zh-CN")}</span>
        </div>
        {(p.status === "returned" || p.status === "rejected") && p.reject_reason && (
          <div className={"pc-reason" + (p.status === "returned" ? " warn" : "")}>
            <b>{p.status === "returned" ? "打回理由" : "拒绝理由"}：</b>{p.reject_reason}
          </div>
        )}
      </a>
    );
  };

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>活动申报</span>
          </nav>
          <div className="page-head-row">
            <div>
              <h1>活动申报</h1>
              <p className="section-sub">发起社团活动、参与投票；或匿名提交意见反馈与举报。</p>
            </div>
            {isLoggedIn && (
              <button className="btn btn-primary" onClick={() => navigate("/activity/new")}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
                新建活动申报
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        {error && (
          <div className="alert alert-danger" style={{ margin: "var(--s-6) 0 var(--s-4)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
            <span>{error}</span>
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
              <div className="fb-hint">无需登录，匿名提交，仅社长可见。</div>
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
                <div><button className="btn btn-primary" type="submit" disabled={fbSubmitting}>{fbSubmitting ? "提交中…" : "匿名提交"}</button></div>
              </form>
            </div>
          )}
        </section>

        {/* 列表区：登录后可见活动申报；社长额外可见反馈 */}
        {!isLoggedIn ? (
          <div className="alert alert-info" style={{ alignItems: "center" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8h.01M11 12h1v4h1" /></svg>
            <span style={{ flex: 1 }}><strong>登录后可查看和参与活动申报、投票</strong></span>
            <button className="btn btn-primary btn-sm" onClick={() => openLogin()}>去登录</button>
          </div>
        ) : (
          <>
            <div className="prop-tabs">
              <div className="seg" role="tablist" aria-label="申报类型">
                <button className="seg-btn" type="button" aria-selected={typeFilter === "activity"} onClick={() => setTypeFilter("activity")}>活动申报</button>
                {isPresident && (
                  <button className="seg-btn" type="button" aria-selected={typeFilter === "feedback"} onClick={() => setTypeFilter("feedback")}>意见反馈</button>
                )}
              </div>
              {isPresident && (
                <span className="lock-note">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="11" width="16" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
                  意见反馈仅社长可见
                </span>
              )}
            </div>

            <div className="prop-filter">
              <div className="input-affix search-affix">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
                <input className="input" type="search" placeholder={typeFilter === "activity" ? "搜索活动申报…" : "搜索意见反馈…"} value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
            </div>

            <div className="filter-bar" role="tablist" aria-label="活动状态" style={{ paddingTop: 0 }}>
              <button className="chip" aria-pressed={statusFilter === ""} onClick={() => setStatusFilter("")}>全部</button>
              {(Object.keys(PROPOSAL_STATUS_LABELS) as (keyof typeof PROPOSAL_STATUS_LABELS)[])
                .filter((s) => typeFilter === "activity" || s !== "voting")
                .map((k) => (
                  <button key={k} className="chip" aria-pressed={statusFilter === k} onClick={() => setStatusFilter(k)}>{PROPOSAL_STATUS_LABELS[k]}</button>
                ))}
            </div>

            {loading ? (
              <p className="muted" style={{ padding: "var(--s-8) 0" }}>加载中…</p>
            ) : proposals.length === 0 ? (
              <div className="prop-empty">
                <p>{typeFilter === "activity" ? "暂无活动申报" : "暂无意见反馈"}</p>
                {typeFilter === "activity" && (
                  <button className="btn btn-primary" onClick={() => navigate("/activity/new")}>发起第一个活动申报</button>
                )}
              </div>
            ) : (
              proposals.map(renderCard)
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
