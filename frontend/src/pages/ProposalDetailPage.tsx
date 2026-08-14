import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { proposalApi } from "../api/proposals";
import { attachmentApi } from "../api/attachments";
import { api } from "../api/client";
import {
  ProposalDetail,
  FEEDBACK_CATEGORY_LABELS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_BADGE_CLASS,
} from "../types/proposals";
import Avatar from "../components/Avatar";
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
  const [attUploading, setAttUploading] = useState(false);
  const [attProgress, setAttProgress] = useState<number | null>(null);

  // 拒绝理由表单（反馈不可打回，仅通过/拒绝）
  const [showReasonForm, setShowReasonForm] = useState(false);
  const [reason, setReason] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.me().then((d) => setCurrentUser({
      id: d.user.id,
      can_approve_proposals: d.user.permissions?.can_approve_proposals,
      can_change_proposals: d.user.permissions?.can_change_proposals,
      can_view_feedback: d.user.permissions?.can_view_feedback,
    })).catch(() => {});
  }, []);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    proposalApi.get(Number(id))
      .then(setProposal)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const canApproveProposals = !!currentUser?.can_approve_proposals;
  const canChangeProposals = !!currentUser?.can_change_proposals;
  const canViewFeedback = !!currentUser?.can_view_feedback;
  const isCreator = !!proposal && !!currentUser && proposal.creator?.id === currentUser.id;

  const handleApprove = async () => {
    if (!proposal) return;
    setActionLoading(true);
    try { setProposal(await proposalApi.approve(proposal.id)); }
    catch (err: any) { setError(err.message); }
    finally { setActionLoading(false); }
  };

  const submitReason = async () => {
    if (!proposal) return;
    const r = reason.trim();
    if (!r) { setError("请填写拒绝理由"); return; }
    setActionLoading(true);
    try {
      setProposal(await proposalApi.reject(proposal.id, r));
      setShowReasonForm(false);
      setReason("");
    } catch (err: any) { setError(err.message); }
    finally { setActionLoading(false); }
  };

  const handleWithdraw = async () => {
    if (!proposal) return;
    if (!window.confirm("确定撤回此反馈吗？")) return;
    setActionLoading(true);
    try { setProposal(await proposalApi.withdraw(proposal.id)); }
    catch (err: any) { setError(err.message); }
    finally { setActionLoading(false); }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !proposal) return;
    setAttUploading(true);
    setAttProgress(null);
    try {
      const att = await attachmentApi.uploadRouted({
        parentType: "proposal", parentId: proposal.id, file, onProgress: setAttProgress,
      });
      if (att) {
        setProposal({ ...proposal, attachments: [...proposal.attachments, att] });
      } else {
        setProposal(await proposalApi.get(proposal.id));
      }
    } catch (err: any) { setError(err.message); }
    finally { setAttUploading(false); setAttProgress(null); }
    e.target.value = "";
  };

  const handleDeleteAttachment = async (attachmentId: number) => {
    if (!proposal) return;
    try {
      await attachmentApi.delete(attachmentId);
      setProposal({ ...proposal, attachments: proposal.attachments.filter((a) => a.id !== attachmentId) });
    } catch (err: any) { setError(err.message); }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  };

  if (loading) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">加载中...</p></div></AppShell>;
  if (error && !proposal) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">{error}</p></div></AppShell>;
  if (!proposal) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">反馈不存在或无权查看</p></div></AppShell>;

  const p = proposal;
  const canApprove = canApproveProposals && p.status === "pending_approval";
  const canWithdraw = isCreator && p.status === "pending_approval";
  // 附件：反馈 carve-out —— 仅署名创建者 + 待审批可传；删除：创建者或 change_proposal（社长能删不能传）
  const canDeleteAttachment = canChangeProposals || isCreator;
  const canUploadAttachment = isCreator && p.status === "pending_approval";

  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/feedback"); }}>意见反馈</a>
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
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/feedback")}>返回列表</button>
            </div>
          </div>
          <p className="detail-sub">
            {FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "反馈"}
            {" · "}提交人 {p.creator ? (p.creator.nickname || p.creator.username) : "匿名"}
            {" · "}{new Date(p.created_at).toLocaleDateString("zh-CN")}
          </p>
        </div>
      </div>

      <div className="container detail-container detail-body">
        {error && <div className="alert alert-danger">{error}</div>}

        {p.status === "rejected" && p.reject_reason && (
          <div className="alert alert-danger"><b>已拒绝：</b>{p.reject_reason}</div>
        )}

        {(canApprove || canWithdraw) && (
          <div className="detail-actions">
            {canWithdraw && (
              <button className="btn btn-ghost" onClick={handleWithdraw} disabled={actionLoading}>撤回</button>
            )}
            {canApprove && (
              <>
                <button className="btn btn-primary" onClick={handleApprove} disabled={actionLoading}>
                  {actionLoading ? "处理中…" : "通过"}
                </button>
                <button className="btn btn-danger" onClick={() => setShowReasonForm(true)} disabled={actionLoading}>拒绝</button>
              </>
            )}
          </div>
        )}

        {showReasonForm && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">拒绝理由</h3>
            <textarea className="textarea" value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="说明拒绝原因..." rows={3} />
            <div className="detail-row">
              <button className="btn btn-primary" onClick={submitReason} disabled={actionLoading}>
                {actionLoading ? "处理中…" : "确认拒绝"}
              </button>
              <button className="btn btn-ghost" onClick={() => { setShowReasonForm(false); setReason(""); }} disabled={actionLoading}>取消</button>
            </div>
          </div>
        )}

        <div className="card card-pad detail-section">
          <h3 className="section-h">基本信息</h3>
          <div className="meta-grid">
            <div className="meta-cell"><span className="meta-k">反馈类别</span><span className="meta-v">{FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "-"}</span></div>
            <div className="meta-cell"><span className="meta-k">提交人</span><span className="meta-v">{p.creator ? (p.creator.nickname || p.creator.username) : "匿名"}</span></div>
            {p.contact && canViewFeedback && (
              <div className="meta-cell"><span className="meta-k">联系方式</span><span className="meta-v">{p.contact}</span></div>
            )}
            <div className="meta-cell"><span className="meta-k">提交时间</span><span className="meta-v">{new Date(p.created_at).toLocaleString("zh-CN")}</span></div>
            {p.reviewed_by && (
              <div className="meta-cell">
                <span className="meta-k">审核人</span>
                <span className="meta-v user-with-avatar"><Link to={`/u/${p.reviewed_by.id}`}><Avatar user={p.reviewed_by} size="sm" /></Link>{p.reviewed_by.nickname || p.reviewed_by.username}</span>
              </div>
            )}
          </div>
        </div>

        <div className="card card-pad detail-section">
          <h3 className="section-h">详细内容</h3>
          {p.description ? (
            <div className="plain-text">{p.description}</div>
          ) : (
            <p className="empty-text">暂无内容</p>
          )}
        </div>

        <div className="card card-pad detail-section">
          <div className="section-head-row">
            <h3 className="section-h">附件 ({p.attachments.length})</h3>
            {canUploadAttachment && (
              <>
                <button className="btn btn-secondary btn-sm" onClick={() => fileInputRef.current?.click()} disabled={attUploading}>+ 上传</button>
                <input ref={fileInputRef} type="file" onChange={handleFileUpload} style={{ display: "none" }} />
              </>
            )}
          </div>
          {attUploading && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "8px 0" }}>
              <span>{attProgress != null ? `上传 ${Math.round(attProgress * 100)}%` : "上传中…"}</span>
              <div style={{ flex: 1, height: 6, background: "#e5e7eb", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: attProgress != null ? `${Math.round(attProgress * 100)}%` : "0%", height: "100%", background: "#2563eb", transition: "width .2s" }} />
              </div>
            </div>
          )}
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
                  {canDeleteAttachment && (
                    <button className="att-del" onClick={() => handleDeleteAttachment(att.id)} title="删除">✕</button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">暂无附件</p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
