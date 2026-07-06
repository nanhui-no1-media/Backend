import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { proposalApi } from "../api/proposals";
import { messagingApi } from "../api/messaging";
import { api } from "../api/client";
import {
  ProposalDetail,
  VoteChoice,
  ACTIVITY_TYPE_LABELS,
  FEEDBACK_CATEGORY_LABELS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_COLORS,
  VOTE_CHOICE_LABELS,
} from "../types/proposals";
import type { Message } from "../types/tasks";
import Avatar from "../components/Avatar";
import RichTextEditor from "../components/RichTextEditor";
import "./Proposals.css";

interface CurrentUser {
  id: number;
  is_president?: boolean;
}

export default function ProposalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [proposal, setProposal] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  // 审批理由表单
  const [showReasonForm, setShowReasonForm] = useState<null | "return" | "reject">(null);
  const [reason, setReason] = useState("");

  // 讨论区
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [message, setMessage] = useState("");
  const [messageSending, setMessageSending] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.me().then((d) => setCurrentUser({ id: d.user.id, is_president: d.user.is_president })).catch(() => {});
  }, []);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    proposalApi.get(Number(id))
      .then((p) => {
        setProposal(p);
        // 仅活动申报开放讨论（反馈无创建人）
        if (p.proposal_type === "activity") {
          messagingApi.getProposalConversation(p.id)
            .then((conv) => {
              setConversationId(conv.id);
              return messagingApi.getMessages(conv.id);
            })
            .then((msgs) => setMessages(msgs.results || msgs))
            .catch(() => {});
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const reload = async () => {
    if (!id) return;
    const p = await proposalApi.get(Number(id));
    setProposal(p);
  };

  const isPresident = !!currentUser?.is_president;
  const isCreator = !!proposal && !!currentUser && proposal.creator?.id === currentUser.id;
  const isActivity = proposal?.proposal_type === "activity";

  const handleVote = async (choice: VoteChoice) => {
    if (!proposal) return;
    setActionLoading(true);
    setError("");
    try {
      const updated = await proposalApi.vote(proposal.id, choice);
      setProposal(updated);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!proposal) return;
    setActionLoading(true);
    try {
      setProposal(await proposalApi.approve(proposal.id));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const submitReason = async () => {
    if (!proposal || !showReasonForm) return;
    const r = reason.trim();
    if (!r) {
      setError("请填写理由");
      return;
    }
    setActionLoading(true);
    try {
      const updated = showReasonForm === "return"
        ? await proposalApi.returnProposal(proposal.id, r)
        : await proposalApi.reject(proposal.id, r);
      setProposal(updated);
      setShowReasonForm(null);
      setReason("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResubmit = async () => {
    if (!proposal) return;
    setActionLoading(true);
    try {
      setProposal(await proposalApi.resubmit(proposal.id));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleWithdraw = async () => {
    if (!proposal) return;
    if (!window.confirm("确定撤回此申报吗？")) return;
    setActionLoading(true);
    try {
      setProposal(await proposalApi.withdraw(proposal.id));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!conversationId || !message.trim()) return;
    setMessageSending(true);
    try {
      const newMsg = await messagingApi.sendMessage(conversationId, message.trim());
      setMessages([...messages, newMsg]);
      setMessage("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setMessageSending(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !proposal) return;
    if (file.size > 50 * 1024 * 1024) {
      setError("文件大小不能超过 50MB");
      return;
    }
    try {
      const att = await proposalApi.addAttachment(proposal.id, file);
      setProposal({ ...proposal, attachments: [...proposal.attachments, att] });
    } catch (err: any) {
      setError(err.message);
    }
    e.target.value = "";
  };

  const handleDeleteAttachment = async (attachmentId: number) => {
    if (!proposal) return;
    try {
      await proposalApi.deleteAttachment(proposal.id, attachmentId);
      setProposal({ ...proposal, attachments: proposal.attachments.filter((a) => a.id !== attachmentId) });
    } catch (err: any) {
      setError(err.message);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  };

  const formatRemaining = (endAt: string | null) => {
    if (!endAt) return "";
    const ms = new Date(endAt).getTime() - Date.now();
    if (ms <= 0) return "已截止";
    const h = Math.floor(ms / 3600000);
    if (h < 24) return `剩余 ${h} 小时`;
    return `剩余 ${Math.floor(h / 24)} 天`;
  };

  if (loading) return <div className="proposal-page"><div className="proposal-loading">加载中...</div></div>;
  if (error && !proposal) return <div className="proposal-page"><div className="proposal-loading">{error}</div></div>;
  if (!proposal) return <div className="proposal-page"><div className="proposal-loading">申报不存在或无权查看</div></div>;

  const p = proposal;
  const summary = {
    approve: p.votes.filter((v) => v.vote_choice === "approve").length,
    oppose: p.votes.filter((v) => v.vote_choice === "oppose").length,
    abstain: p.votes.filter((v) => v.vote_choice === "abstain").length,
  };
  const canVote = isActivity && p.status === "voting" && currentUser && p.my_vote === null;
  const canApprove = isPresident && p.status === "pending_approval";
  const canEdit = isActivity && p.status === "returned" && (isCreator || isPresident);
  const canResubmit = isActivity && p.status === "returned" && (isCreator || isPresident);
  const canWithdraw = isCreator && (p.status === "voting" || p.status === "pending_approval");
  const canManageAttachment = isActivity && (isPresident || isCreator);

  return (
    <div className="proposal-page">
      <div className="proposal-detail-container">
        <div className="proposal-detail-header">
          <button className="proposal-back" onClick={() => navigate("/activity")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
            </svg>
            返回列表
          </button>
          {canEdit && (
            <button className="proposal-btn-secondary" onClick={() => navigate(`/activity/${p.id}/edit`)}>
              编辑
            </button>
          )}
        </div>

        {error && <div className="proposal-error">{error}</div>}

        <div className="proposal-detail-title-row">
          <h1 className="proposal-detail-title">{p.title}</h1>
          <span
            className="proposal-status-badge"
            style={{
              backgroundColor: (PROPOSAL_STATUS_COLORS[p.status] || "#6b7280") + "18",
              color: PROPOSAL_STATUS_COLORS[p.status] || "#6b7280",
              fontSize: "14px",
              padding: "6px 14px",
              borderRadius: "8px",
              fontWeight: 600,
            }}
          >
            {PROPOSAL_STATUS_LABELS[p.status]}
          </span>
        </div>

        {(p.status === "returned" || p.status === "rejected") && p.reject_reason && (
          <div className="returned-banner">
            ⚠ {p.status === "returned" ? "已打回" : "已拒绝"}：{p.reject_reason}
          </div>
        )}

        <div className="proposal-detail-meta">
          {isActivity ? (
            <div className="meta-item">
              <span className="meta-label">活动类型</span>
              <span>{ACTIVITY_TYPE_LABELS[p.activity_type as keyof typeof ACTIVITY_TYPE_LABELS] || "-"}</span>
            </div>
          ) : (
            <div className="meta-item">
              <span className="meta-label">反馈类别</span>
              <span>{FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "-"}</span>
            </div>
          )}
          <div className="meta-item">
            <span className="meta-label">{isActivity ? "申报人" : "提交人"}</span>
            <span className="user-with-avatar">
              {p.creator ? (
                <>
                  <Avatar user={p.creator} />
                  {p.creator.nickname || p.creator.username}
                </>
              ) : "匿名"}
            </span>
          </div>
          {isActivity && (
            <>
              <div className="meta-item">
                <span className="meta-label">拟办日期</span>
                <span>{p.planned_date || "-"}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">地点</span>
                <span>{p.location || "-"}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">预计人数</span>
                <span>{p.expected_participants != null ? p.expected_participants : "-"}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">预算</span>
                <span>{p.budget != null ? `¥${p.budget}` : "-"}</span>
              </div>
            </>
          )}
          {!isActivity && p.contact && isPresident && (
            <div className="meta-item">
              <span className="meta-label">联系方式</span>
              <span>{p.contact}</span>
            </div>
          )}
          <div className="meta-item">
            <span className="meta-label">提交时间</span>
            <span>{new Date(p.created_at).toLocaleString("zh-CN")}</span>
          </div>
          {p.reviewed_by && (
            <div className="meta-item">
              <span className="meta-label">审核人</span>
              <span className="user-with-avatar">
                <Avatar user={p.reviewed_by} />
                {p.reviewed_by.nickname || p.reviewed_by.username}
              </span>
            </div>
          )}
        </div>

        {/* 操作按钮行 */}
        {(canVote || canApprove || canResubmit || canWithdraw) && (
          <div className="proposal-actions-row">
            {canResubmit && (
              <button className="proposal-btn-primary" onClick={handleResubmit} disabled={actionLoading}>
                {actionLoading ? "处理中..." : "重新提交（开始投票）"}
              </button>
            )}
            {canWithdraw && (
              <button className="proposal-btn-danger" onClick={handleWithdraw} disabled={actionLoading}>
                撤回
              </button>
            )}
            {canApprove && (
              <>
                <button className="proposal-btn-primary" onClick={handleApprove} disabled={actionLoading}>
                  {actionLoading ? "处理中..." : "通过"}
                </button>
                <button className="proposal-btn-secondary" onClick={() => setShowReasonForm("return")} disabled={actionLoading}>
                  打回
                </button>
                <button className="proposal-btn-danger" onClick={() => setShowReasonForm("reject")} disabled={actionLoading}>
                  拒绝
                </button>
              </>
            )}
          </div>
        )}

        {showReasonForm && (
          <div className="reason-form">
            <h3>{showReasonForm === "return" ? "打回理由" : "拒绝理由"}</h3>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={showReasonForm === "return" ? "说明需要修改的内容..." : "说明拒绝原因..."}
              rows={3}
            />
            <div className="reason-form-actions">
              <button className="proposal-btn-primary" onClick={submitReason} disabled={actionLoading}>
                {actionLoading ? "处理中..." : `确认${showReasonForm === "return" ? "打回" : "拒绝"}`}
              </button>
              <button
                className="proposal-btn-secondary"
                onClick={() => { setShowReasonForm(null); setReason(""); }}
                disabled={actionLoading}
              >
                取消
              </button>
            </div>
          </div>
        )}

        {/* 描述 */}
        <div className="proposal-detail-section">
          <h3>详细说明</h3>
          {p.description ? (
            isActivity ? (
              <div className="proposal-description rich">
                <RichTextEditor content={p.description} editable={false} />
              </div>
            ) : (
              <div className="proposal-description">{p.description}</div>
            )
          ) : (
            <p className="proposal-empty-text">暂无说明</p>
          )}
        </div>

        {/* 投票区（仅活动申报） */}
        {isActivity && (
          <div className="proposal-detail-section">
            <h3>投票</h3>
            <div className="vote-box">
              {p.status === "voting" && (
                <div className="vote-deadline">
                  投票进行中，<strong>{formatRemaining(p.voting_end_at)}</strong>（公开实名，每人一次，不可修改；结果仅供参考，社长最终决定）
                </div>
              )}
              {p.status !== "voting" && (
                <div className="vote-deadline">投票已结束（共 {p.votes.length} 票）</div>
              )}

              <div className="vote-summary">
                <div className="vote-summary-item">
                  <span className="vote-summary-num approve">{summary.approve}</span>
                  <span className="vote-summary-label">赞成</span>
                </div>
                <div className="vote-summary-item">
                  <span className="vote-summary-num oppose">{summary.oppose}</span>
                  <span className="vote-summary-label">反对</span>
                </div>
                <div className="vote-summary-item">
                  <span className="vote-summary-num abstain">{summary.abstain}</span>
                  <span className="vote-summary-label">弃权</span>
                </div>
              </div>

              {canVote ? (
                <div className="vote-actions">
                  <button className="vote-btn approve" onClick={() => handleVote("approve")} disabled={actionLoading}>
                    {VOTE_CHOICE_LABELS.approve}
                  </button>
                  <button className="vote-btn oppose" onClick={() => handleVote("oppose")} disabled={actionLoading}>
                    {VOTE_CHOICE_LABELS.oppose}
                  </button>
                  <button className="vote-btn abstain" onClick={() => handleVote("abstain")} disabled={actionLoading}>
                    {VOTE_CHOICE_LABELS.abstain}
                  </button>
                </div>
              ) : p.my_vote ? (
                <div className="vote-cast-hint">
                  你已投：<strong>{VOTE_CHOICE_LABELS[p.my_vote]}</strong>（不可修改）
                </div>
              ) : p.status === "voting" ? (
                <div className="vote-cast-hint proposal-empty-text">登录后可参与投票</div>
              ) : null}

              {p.votes.length > 0 && (
                <div className="vote-list">
                  {p.votes.map((v) => (
                    <div key={v.id} className="vote-item">
                      <Avatar user={v.voter} />
                      <span>{v.voter.nickname || v.voter.username}</span>
                      <span className={`vote-item-choice ${v.vote_choice}`}>
                        {VOTE_CHOICE_LABELS[v.vote_choice]}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 附件（仅活动申报；反馈为匿名无附件） */}
        {isActivity && (
          <div className="proposal-detail-section">
            <div className="section-header">
              <h3>附件 ({p.attachments.length})</h3>
              {canManageAttachment && (
                <>
                  <button className="proposal-btn-secondary proposal-btn-sm" onClick={() => fileInputRef.current?.click()}>
                    + 上传
                  </button>
                  <input ref={fileInputRef} type="file" onChange={handleFileUpload} style={{ display: "none" }} />
                </>
              )}
            </div>
            {p.attachments.length > 0 ? (
              <div className="attachment-list">
                {p.attachments.map((att) => (
                  <div key={att.id} className="attachment-item">
                    <span className="attachment-icon">
                      {att.file_type === "image" ? "IMG" :
                       att.file_type === "video" ? "VID" :
                       att.file_type === "document" ? "DOC" :
                       att.file_type === "archive" ? "ZIP" : "FILE"}
                    </span>
                    <a href={att.file_url} target="_blank" rel="noopener noreferrer" className="attachment-name">
                      {att.file_name}
                    </a>
                    <span className="attachment-size">{formatSize(att.file_size)}</span>
                    {canManageAttachment && (
                      <button className="attachment-delete" onClick={() => handleDeleteAttachment(att.id)} title="删除">✕</button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="proposal-empty-text">暂无附件</p>
            )}
          </div>
        )}

        {/* 讨论（仅活动申报） */}
        {isActivity && (
          <div className="proposal-detail-section">
            <h3>讨论 ({messages.length})</h3>
            {conversationId && (
              <div className="comment-input">
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="输入消息，使用 @用户名 提及他人..."
                  rows={3}
                />
                <button
                  className="proposal-btn-primary proposal-btn-sm"
                  onClick={handleSendMessage}
                  disabled={!message.trim() || messageSending}
                >
                  {messageSending ? "发送中..." : "发送"}
                </button>
              </div>
            )}
            {messages.length > 0 ? (
              <div className="comment-list">
                {messages.map((m) => (
                  <div key={m.id} className="comment-item">
                    <div className="comment-header">
                      <Avatar user={m.sender} size="md" />
                      <strong>{m.sender.nickname || m.sender.username}</strong>
                      <span className="comment-time">{new Date(m.created_at).toLocaleString("zh-CN")}</span>
                    </div>
                    <div className="comment-content">{m.content}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="proposal-empty-text">暂无讨论</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
