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
  PROPOSAL_STATUS_COLORS,
  ACTIVITY_TYPE_LABELS,
  FEEDBACK_CATEGORY_LABELS,
} from "../types/proposals";
import Avatar from "../components/Avatar";
import "./Proposals.css";

interface CurrentUser {
  id: number;
  username: string;
  is_president?: boolean;
}

export default function ProposalListPage() {
  const navigate = useNavigate();
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
    return (
      <div key={p.id} className="proposal-card" onClick={() => navigate(`/activity/${p.id}`)}>
        <div className="proposal-card-title">{p.title}</div>
        <div className="proposal-card-meta">
          <span
            className="proposal-status-badge"
            style={{
              backgroundColor: (PROPOSAL_STATUS_COLORS[p.status] || "#6b7280") + "18",
              color: PROPOSAL_STATUS_COLORS[p.status] || "#6b7280",
            }}
          >
            {PROPOSAL_STATUS_LABELS[p.status]}
          </span>
          <span className={`proposal-type-tag${isActivity ? "" : " feedback"}`}>
            {isActivity
              ? ACTIVITY_TYPE_LABELS[p.activity_type as keyof typeof ACTIVITY_TYPE_LABELS] || "活动申报"
              : `🔒 ${FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "意见反馈"}`}
          </span>
          <span className="proposal-meta-text user-with-avatar">
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
            <span className="proposal-card-vote">
              <span className="vote-mini">赞成 {p.vote_summary.approve}</span>
              <span className="vote-mini oppose">反对 {p.vote_summary.oppose}</span>
              <span className="vote-mini abstain">弃权 {p.vote_summary.abstain}</span>
            </span>
          )}
          {isActivity && p.status === "voting" && (
            <span className="proposal-meta-text">⏱ {formatRemaining(p.voting_end_at)}</span>
          )}
          {p.attachment_count > 0 && <span className="proposal-meta-text">{p.attachment_count} 附件</span>}
          <span className="proposal-meta-text">{new Date(p.created_at).toLocaleDateString("zh-CN")}</span>
        </div>
        {(p.status === "returned" || p.status === "rejected") && p.reject_reason && (
          <div className="proposal-card-reason">
            {p.status === "returned" ? "打回理由" : "拒绝理由"}：{p.reject_reason}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="proposal-page">
      <div className="proposal-container">
        {/* Header */}
        <div className="proposal-header">
          <button className="proposal-back" onClick={() => navigate("/")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
            </svg>
            主页
          </button>
          <h1 className="proposal-title">活动申报 / 意见反馈</h1>
          {isLoggedIn && (
            <button className="proposal-btn-primary" onClick={() => navigate("/activity/new")}>
              + 新建活动申报
            </button>
          )}
        </div>

        {error && <div className="proposal-error">{error}</div>}

        {/* 公开匿名反馈表单：所有人均可提交 */}
        <div className="feedback-section">
          <div
            className="feedback-section-header"
            onClick={() => setShowFeedbackForm((v) => !v)}
            role="button"
            tabIndex={0}
          >
            <div>
              <div className="feedback-section-title">📝 提交意见反馈 / 举报</div>
              <div className="feedback-anonymous-hint">
                无需登录，匿名提交，仅社长可见。
              </div>
            </div>
            <button className="proposal-btn-secondary proposal-btn-sm">
              {showFeedbackForm ? "收起" : "展开"}
            </button>
          </div>

          {showFeedbackForm && (
            <form className="feedback-form" onSubmit={submitFeedback}>
              {fbSuccess && (
                <div className="feedback-success">✅ 已提交，感谢你的反馈！</div>
              )}
              <div className="form-row">
                <div className="form-field">
                  <label>类别</label>
                  <select
                    value={fbCategory}
                    onChange={(e) => setFbCategory(e.target.value as FeedbackCategory)}
                  >
                    {(Object.keys(FEEDBACK_CATEGORY_LABELS) as FeedbackCategory[]).map((k) => (
                      <option key={k} value={k}>{FEEDBACK_CATEGORY_LABELS[k]}</option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label>联系方式 <span className="hint">（选填）</span></label>
                  <input
                    type="text"
                    value={fbContact}
                    onChange={(e) => setFbContact(e.target.value)}
                    placeholder="如需回复请留下联系方式"
                    maxLength={100}
                  />
                </div>
              </div>
              <div className="form-field">
                <label>标题 *</label>
                <input
                  type="text"
                  value={fbTitle}
                  onChange={(e) => setFbTitle(e.target.value)}
                  placeholder="一句话概括"
                  maxLength={200}
                  required
                />
              </div>
              <div className="form-field">
                <label>详细内容 *</label>
                <textarea
                  value={fbDesc}
                  onChange={(e) => setFbDesc(e.target.value)}
                  placeholder="详细描述你的建议 / 投诉 / 举报内容..."
                  rows={4}
                  required
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="proposal-btn-primary" disabled={fbSubmitting}>
                  {fbSubmitting ? "提交中..." : "匿名提交"}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* 列表区：登录后可见活动申报；社长额外可见反馈 */}
        {!isLoggedIn ? (
          <div className="proposal-notice">
            <strong>登录后可查看和参与活动申报、投票</strong>
            <button className="proposal-btn-primary" onClick={() => navigate("/login")}>去登录</button>
          </div>
        ) : (
          <>
            <div className="proposal-tabs">
              <button
                className={`proposal-tab${typeFilter === "activity" ? " active" : ""}`}
                onClick={() => setTypeFilter("activity")}
              >
                活动申报
              </button>
              {isPresident && (
                <button
                  className={`proposal-tab${typeFilter === "feedback" ? " active" : ""}`}
                  onClick={() => setTypeFilter("feedback")}
                >
                  意见反馈（社长）
                </button>
              )}
            </div>

            <div className="proposal-filters">
              <input
                type="text"
                className="proposal-search"
                placeholder={typeFilter === "activity" ? "搜索活动申报..." : "搜索意见反馈..."}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="proposal-select"
              >
                <option value="">全部状态</option>
                {(Object.keys(PROPOSAL_STATUS_LABELS) as (keyof typeof PROPOSAL_STATUS_LABELS)[])
                  .filter((s) => typeFilter === "activity" || s !== "voting")
                  .map((k) => (
                    <option key={k} value={k}>{PROPOSAL_STATUS_LABELS[k]}</option>
                  ))}
              </select>
            </div>

            {loading ? (
              <div className="proposal-loading">加载中...</div>
            ) : proposals.length === 0 ? (
              <div className="proposal-empty">
                <p>{typeFilter === "activity" ? "暂无活动申报" : "暂无意见反馈"}</p>
                {typeFilter === "activity" && (
                  <button className="proposal-btn-primary" onClick={() => navigate("/activity/new")}>
                    发起第一个活动申报
                  </button>
                )}
              </div>
            ) : (
              <div className="proposal-list">{proposals.map(renderCard)}</div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
