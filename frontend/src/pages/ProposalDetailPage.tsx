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
  PROPOSAL_STATUS_BADGE_CLASS,
  VOTE_CHOICE_LABELS,
} from "../types/proposals";
import type { Message } from "../types/tasks";
import Avatar from "../components/Avatar";
import RichTextEditor from "../components/RichTextEditor";
import AppShell from "../components/AppShell";
import "../styles/detail.css";

interface CurrentUser {
  id: number;
  can_approve_proposals?: boolean;
  can_change_proposals?: boolean;
  can_view_feedback?: boolean;
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
    api.me().then((d) => setCurrentUser({
      id: d.user.id,
      can_approve_proposals: d.user.permissions?.can_approve_proposals,
      can_change_proposals: d.user.permissions?.can_change_proposals,
      can_view_feedback: d.user.permissions?.can_view_feedback
    })).catch(() => {});
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

  const canApproveProposals = !!currentUser?.can_approve_proposals;
  const canChangeProposals = !!currentUser?.can_change_proposals;
  const canViewFeedback = !!currentUser?.can_view_feedback;
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

  if (loading) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">加载中...</p></div></AppShell>;
  if (error && !proposal) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">{error}</p></div></AppShell>;
  if (!proposal) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">申报不存在或无权查看</p></div></AppShell>;

  const p = proposal;
  const summary = {
    approve: p.votes.filter((v) => v.vote_choice === "approve").length,
    oppose: p.votes.filter((v) => v.vote_choice === "oppose").length,
    abstain: p.votes.filter((v) => v.vote_choice === "abstain").length,
  };
  const canVote = isActivity && p.status === "voting" && currentUser && p.my_vote === null;
  const canApprove = canApproveProposals && p.status === "pending_approval";
  const canEdit = isActivity && p.status === "returned" && (isCreator || canChangeProposals);
  const canResubmit = isActivity && p.status === "returned" && (isCreator || canChangeProposals);
  const canWithdraw = isCreator && (p.status === "voting" || p.status === "pending_approval");
  const canManageAttachment = isActivity && (canChangeProposals || isCreator);

  const pct = (n: number, total: number) => (total > 0 ? Math.round((n / total) * 100) : 0) + "%";

  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动申报</a>
            <span className="sep">/</span>
            <span>{p.title}</span>
          </nav>
          <div className="detail-head-row">
            <div className="detail-head-main">
              <h1 className="detail-title">{p.title}</h1>
              <span className={"badge " + PROPOSAL_STATUS_BADGE_CLASS[p.status]}>
                <span className="badge-dot" />{PROPOSAL_STATUS_LABELS[p.status]}
              </span>
            </div>
            <div className="detail-head-actions">
              {canEdit && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/activity/${p.id}/edit`)}>编辑</button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/activity")}>返回列表</button>
            </div>
          </div>
          <p className="detail-sub">
            {isActivity
              ? (ACTIVITY_TYPE_LABELS[p.activity_type as keyof typeof ACTIVITY_TYPE_LABELS] || "活动")
              : (FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "反馈")}
            {" · "}{isActivity ? "申报人" : "提交人"} {p.creator ? (p.creator.nickname || p.creator.username) : "匿名"}
            {" · "}{new Date(p.created_at).toLocaleDateString("zh-CN")}
            {isActivity && p.status === "voting" && p.voting_end_at ? " · " + formatRemaining(p.voting_end_at) : ""}
          </p>
        </div>
      </div>

      <div className="container detail-container detail-body">
        {error && <div className="alert alert-danger">{error}</div>}

        {(p.status === "returned" || p.status === "rejected") && p.reject_reason && (
          <div className="alert alert-danger">
            <b>{p.status === "returned" ? "已打回" : "已拒绝"}：</b>{p.reject_reason}
          </div>
        )}

        {(canVote || canApprove || canResubmit || canWithdraw) && (
          <div className="detail-actions">
            {canResubmit && (
              <button className="btn btn-primary" onClick={handleResubmit} disabled={actionLoading}>
                {actionLoading ? "处理中…" : "重新提交（开始投票）"}
              </button>
            )}
            {canWithdraw && (
              <button className="btn btn-ghost" onClick={handleWithdraw} disabled={actionLoading}>撤回</button>
            )}
            {canApprove && (
              <>
                <button className="btn btn-primary" onClick={handleApprove} disabled={actionLoading}>
                  {actionLoading ? "处理中…" : "通过"}
                </button>
                <button className="btn btn-ghost" onClick={() => setShowReasonForm("return")} disabled={actionLoading}>打回</button>
                <button className="btn btn-danger" onClick={() => setShowReasonForm("reject")} disabled={actionLoading}>拒绝</button>
              </>
            )}
          </div>
        )}

        {showReasonForm && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">{showReasonForm === "return" ? "打回理由" : "拒绝理由"}</h3>
            <textarea className="textarea" value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder={showReasonForm === "return" ? "说明需要修改的内容..." : "说明拒绝原因..."}
                      rows={3} />
            <div className="detail-row">
              <button className="btn btn-primary" onClick={submitReason} disabled={actionLoading}>
                {actionLoading ? "处理中…" : `确认${showReasonForm === "return" ? "打回" : "拒绝"}`}
              </button>
              <button className="btn btn-ghost"
                      onClick={() => { setShowReasonForm(null); setReason(""); }}
                      disabled={actionLoading}>取消</button>
            </div>
          </div>
        )}

        <div className="card card-pad detail-section">
          <h3 className="section-h">基本信息</h3>
          <div className="meta-grid">
            {isActivity ? (
              <>
                <div className="meta-cell"><span className="meta-k">活动类型</span><span className="meta-v">{ACTIVITY_TYPE_LABELS[p.activity_type as keyof typeof ACTIVITY_TYPE_LABELS] || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">拟办日期</span><span className="meta-v">{p.planned_date || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">地点</span><span className="meta-v">{p.location || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">预计人数</span><span className="meta-v">{p.expected_participants != null ? p.expected_participants : "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">预算</span><span className="meta-v">{p.budget != null ? `¥${p.budget}` : "-"}</span></div>
              </>
            ) : (
              <>
                <div className="meta-cell"><span className="meta-k">反馈类别</span><span className="meta-v">{FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">提交人</span><span className="meta-v">匿名</span></div>
                {!isActivity && p.contact && canViewFeedback && (
                  <div className="meta-cell"><span className="meta-k">联系方式</span><span className="meta-v">{p.contact}</span></div>
                )}
              </>
            )}
            <div className="meta-cell"><span className="meta-k">提交时间</span><span className="meta-v">{new Date(p.created_at).toLocaleString("zh-CN")}</span></div>
            {p.reviewed_by && (
              <div className="meta-cell">
                <span className="meta-k">审核人</span>
                <span className="meta-v user-with-avatar"><Avatar user={p.reviewed_by} size="sm" />{p.reviewed_by.nickname || p.reviewed_by.username}</span>
              </div>
            )}
          </div>
        </div>

        <div className="card card-pad detail-section">
          <h3 className="section-h">详细说明</h3>
          {p.description ? (
            isActivity ? (
              <RichTextEditor content={p.description} editable={false} />
            ) : (
              <div className="plain-text">{p.description}</div>
            )
          ) : (
            <p className="empty-text">暂无说明</p>
          )}
        </div>

        {isActivity && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">投票</h3>
            <div className="vote-deadline">
              {p.status === "voting"
                ? <>投票进行中，<strong>{formatRemaining(p.voting_end_at)}</strong>（公开实名，每人一次，不可修改；结果仅供参考，社长最终决定）</>
                : <>投票已结束（共 {p.votes.length} 票）</>}
            </div>
            <div className="votebar">
              <i className="app" style={{ width: pct(summary.approve, p.votes.length) }} />
              <i className="opp" style={{ width: pct(summary.oppose, p.votes.length) }} />
              <i className="abs" style={{ width: pct(summary.abstain, p.votes.length) }} />
            </div>
            <div className="vote-num">
              <span className="app">赞成 {summary.approve}</span>
              <span className="opp">反对 {summary.oppose}</span>
              <span className="abs">弃权 {summary.abstain}</span>
            </div>
            {canVote ? (
              <div className="vote-actions">
                <button className="btn vote-btn approve" onClick={() => handleVote("approve")} disabled={actionLoading}>{VOTE_CHOICE_LABELS.approve}</button>
                <button className="btn vote-btn oppose" onClick={() => handleVote("oppose")} disabled={actionLoading}>{VOTE_CHOICE_LABELS.oppose}</button>
                <button className="btn vote-btn abstain" onClick={() => handleVote("abstain")} disabled={actionLoading}>{VOTE_CHOICE_LABELS.abstain}</button>
              </div>
            ) : p.my_vote ? (
              <div className="vote-cast-hint">你已投：<strong>{VOTE_CHOICE_LABELS[p.my_vote]}</strong>（不可修改）</div>
            ) : p.status === "voting" ? (
              <div className="empty-text">登录后可参与投票</div>
            ) : null}
            {p.votes.length > 0 && (
              <div className="vote-list">
                {p.votes.map((v) => (
                  <div key={v.id} className="vote-item">
                    <Avatar user={v.voter} size="sm" />
                    <span className="vote-name">{v.voter.nickname || v.voter.username}</span>
                    <span className={"vote-choice " + v.vote_choice}>{VOTE_CHOICE_LABELS[v.vote_choice]}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {isActivity && (
          <div className="card card-pad detail-section">
            <div className="section-head-row">
              <h3 className="section-h">附件 ({p.attachments.length})</h3>
              {canManageAttachment && (
                <>
                  <button className="btn btn-secondary btn-sm" onClick={() => fileInputRef.current?.click()}>+ 上传</button>
                  <input ref={fileInputRef} type="file" onChange={handleFileUpload} style={{ display: "none" }} />
                </>
              )}
            </div>
            {p.attachments.length > 0 ? (
              <div className="att-list">
                {p.attachments.map((att) => (
                  <div key={att.id} className="att-item">
                    <span className="att-icon">
                      {att.file_type === "image" ? "IMG" : att.file_type === "video" ? "VID" :
                       att.file_type === "document" ? "DOC" : att.file_type === "archive" ? "ZIP" : "FILE"}
                    </span>
                    <a href={att.file_url} target="_blank" rel="noopener noreferrer" className="att-name">{att.file_name}</a>
                    <span className="att-size">{formatSize(att.file_size)}</span>
                    {canManageAttachment && (
                      <button className="att-del" onClick={() => handleDeleteAttachment(att.id)} title="删除">✕</button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-text">暂无附件</p>
            )}
          </div>
        )}

        {isActivity && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">讨论 ({messages.length})</h3>
            {conversationId && (
              <div className="comment-input">
                <textarea className="textarea" value={message}
                          onChange={(e) => setMessage(e.target.value)}
                          placeholder="输入消息，使用 @用户名 提及他人..." rows={3} />
                <button className="btn btn-primary btn-sm"
                        onClick={handleSendMessage}
                        disabled={!message.trim() || messageSending}>
                  {messageSending ? "发送中…" : "发送"}
                </button>
              </div>
            )}
            {messages.length > 0 ? (
              <div className="comment-list">
                {messages.map((m) => (
                  <div key={m.id} className="comment-item">
                    <div className="comment-head">
                      <Avatar user={m.sender} size="md" />
                      <strong>{m.sender.nickname || m.sender.username}</strong>
                      <span className="comment-time">{new Date(m.created_at).toLocaleString("zh-CN")}</span>
                    </div>
                    <div className="comment-content">{m.content}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-text">暂无讨论</p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
