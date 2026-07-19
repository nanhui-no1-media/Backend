import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { taskApi } from "../api/tasks";
import { messagingApi } from "../api/messaging";
import { api } from "../api/client";
import {
  TaskDetail, Message,
  STATUS_LABELS, PRIORITY_LABELS,
  STATUS_BADGE_CLASS, PRIORITY_DOT_CLASS,
} from "../types/tasks";
import RichTextEditor from "../components/RichTextEditor";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";
import "../styles/detail.css";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [messageSubmitting, setMessageSubmitting] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [claimReason, setClaimReason] = useState("");
  const [claiming, setClaiming] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<{ id: number; can_manage_tasks?: boolean } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  useEffect(() => {
    api.me().then((d) => setCurrentUser({ id: d.user.id, can_manage_tasks: d.user.permissions?.can_manage_tasks })).catch(() => {});
  }, []);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    taskApi.get(Number(id))
      .then((t) => {
        setTask(t);
        messagingApi.getTaskConversation(t.id)
          .then((conv) => {
            setConversationId(conv.id);
            return messagingApi.getMessages(conv.id);
          })
          .then((msgs) => setMessages(msgs.results || msgs))
          .catch(() => {});
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const reloadTask = async () => {
    if (!task) return;
    const updated = await taskApi.get(task.id);
    setTask(updated);
  };

  const handleSendMessage = async () => {
    if (!conversationId || !message.trim()) return;
    setMessageSubmitting(true);
    try {
      const newMsg = await messagingApi.sendMessage(conversationId, message.trim());
      setMessages([...messages, newMsg]);
      setMessage("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setMessageSubmitting(false);
    }
  };

  const handleClaim = async () => {
    if (!task) return;
    setClaiming(true);
    try {
      await taskApi.claim(task.id, claimReason);
      await reloadTask();
      setClaimReason("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setClaiming(false);
    }
  };

  const handleApproveClaim = async (claimId: number) => {
    if (!task) return;
    setActionLoading(true);
    try {
      const updated = await taskApi.approveClaim(task.id, claimId);
      setTask(updated);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectClaim = async (claimId: number) => {
    if (!task) return;
    setActionLoading(true);
    try {
      await taskApi.rejectClaim(task.id, claimId);
      await reloadTask();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      const updated = await taskApi.complete(task.id);
      setTask(updated);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveCompletion = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      const updated = await taskApi.approveCompletion(task.id);
      setTask(updated);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectCompletion = async () => {
    if (!task) return;
    const reason = rejectReason.trim();
    if (!reason) {
      setError("请填写打回理由");
      return;
    }
    setActionLoading(true);
    try {
      const updated = await taskApi.rejectCompletion(task.id, reason);
      setTask(updated);
      setShowRejectForm(false);
      setRejectReason("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      const updated = await taskApi.cancel(task.id);
      setTask(updated);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !task) return;
    if (file.size > 50 * 1024 * 1024) {
      setError("文件大小不能超过 50MB");
      return;
    }
    try {
      const att = await taskApi.addAttachment(task.id, file);
      setTask({ ...task, attachments: [...task.attachments, att] });
    } catch (err: any) {
      setError(err.message);
    }
    e.target.value = "";
  };

  const handleDeleteAttachment = async (attachmentId: number) => {
    if (!task) return;
    try {
      await taskApi.deleteAttachment(task.id, attachmentId);
      setTask({ ...task, attachments: task.attachments.filter((a) => a.id !== attachmentId) });
    } catch (err: any) {
      setError(err.message);
    }
  };

  const formatDate = (d: string | null) => {
    if (!d) return "-";
    return new Date(d).toLocaleDateString("zh-CN");
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  };

  const isCreator = task && currentUser && task.creator.id === currentUser.id;
  const canManageTasks = !!currentUser?.can_manage_tasks;
  const isAssignee = task && currentUser && task.assignee?.id === currentUser.id;
  const canClaim = task && !task.assignee && currentUser && task.creator.id !== currentUser.id && task.status === "pending";
  const canComplete = task && task.status === "in_progress" && (!!isAssignee || canManageTasks);
  const canReviewCompletion = task && task.status === "reviewing" && (!!isCreator || canManageTasks);
  const canCancel = task && task.status !== "completed" && task.status !== "cancelled" && (!!isCreator || canManageTasks);
  const pendingClaims = task?.claim_requests.filter((c) => c.status === "pending") || [];

  if (loading) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">加载中...</p></div></AppShell>;
  if (error && !task) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">{error}</p></div></AppShell>;
  if (!task) return <AppShell><div className="container detail-container detail-body"><p className="empty-text">任务不存在</p></div></AppShell>;

  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/tasks"); }}>任务</a>
            <span className="sep">/</span>
            <span>{task.title}</span>
          </nav>
          <div className="detail-head-row">
            <div className="detail-head-main">
              <span className={"prio-dot " + PRIORITY_DOT_CLASS[task.priority]}
                    title={"优先级：" + PRIORITY_LABELS[task.priority]} />
              <h1 className="detail-title">{task.title}</h1>
              <span className={"badge " + STATUS_BADGE_CLASS[task.status]}>
                <span className="badge-dot" />{STATUS_LABELS[task.status]}
              </span>
            </div>
            <div className="detail-head-actions">
              {task.status === "pending" && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/tasks/${task.id}/edit`)}>编辑</button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/tasks")}>返回列表</button>
            </div>
          </div>
          <p className="detail-sub">
            {PRIORITY_LABELS[task.priority]} · 创建人 {task.creator.nickname || task.creator.username}
            {" · 负责人 "}{task.assignee ? (task.assignee.nickname || task.assignee.username) : "未分配"}
            {" · "}{formatDate(task.created_at)}
          </p>
        </div>
      </div>

      <div className="container detail-container detail-body">
        {error && <div className="alert alert-danger">{error}</div>}

        {task.status === "in_progress" && task.reject_reason && (
          <div className="alert alert-warning"><b>此任务已被打回：</b>{task.reject_reason}</div>
        )}

        {(canComplete || canReviewCompletion || canCancel) && (
          <div className="detail-actions">
            {canComplete && (
              <button className="btn btn-primary" onClick={handleComplete} disabled={actionLoading}>
                {actionLoading ? "处理中…" : "提交验收"}
              </button>
            )}
            {canReviewCompletion && (
              <>
                <button className="btn btn-primary" onClick={handleApproveCompletion} disabled={actionLoading}>通过验收</button>
                <button className="btn btn-ghost" onClick={() => setShowRejectForm(true)} disabled={actionLoading}>打回</button>
              </>
            )}
            {canCancel && (
              <button className="btn btn-ghost" onClick={handleCancel} disabled={actionLoading}>取消任务</button>
            )}
          </div>
        )}

        {showRejectForm && canReviewCompletion && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">打回理由</h3>
            <textarea className="textarea" value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="说明打回原因，告知负责人需返工的内容..." rows={3} />
            <div className="detail-row">
              <button className="btn btn-primary" onClick={handleRejectCompletion} disabled={actionLoading}>
                {actionLoading ? "处理中…" : "确认打回"}
              </button>
              <button className="btn btn-ghost"
                      onClick={() => { setShowRejectForm(false); setRejectReason(""); }}
                      disabled={actionLoading}>取消</button>
            </div>
          </div>
        )}

        {task.tags.length > 0 && (
          <div className="detail-tags">
            {task.tags.map((t) => (
              <span key={t.id} className="tag-mini" style={{ backgroundColor: t.color + "1a", color: t.color }}>{t.name}</span>
            ))}
          </div>
        )}

        <div className="card card-pad detail-section">
          <h3 className="section-h">描述</h3>
          {task.description ? (
            <RichTextEditor content={task.description} editable={false} />
          ) : (
            <p className="empty-text">暂无描述</p>
          )}
        </div>

        {task.collaborators.length > 0 && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">协作者</h3>
            <div className="chip-row">
              {task.collaborators.map((u) => (
                <span key={u.id} className="user-chip-inline">
                  <Avatar user={u} size="sm" />{u.nickname || u.username}
                </span>
              ))}
            </div>
          </div>
        )}

        {canClaim && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">认领任务</h3>
            <textarea className="textarea" value={claimReason}
                      onChange={(e) => setClaimReason(e.target.value)}
                      placeholder="说明你想认领此任务的理由..." rows={2} />
            <button className="btn btn-primary" onClick={handleClaim} disabled={claiming}>
              {claiming ? "提交中…" : "申请认领"}
            </button>
          </div>
        )}

        {(!!isCreator || canManageTasks) && pendingClaims.length > 0 && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">认领请求 ({pendingClaims.length})</h3>
            <div className="claim-list">
              {pendingClaims.map((cr) => (
                <div key={cr.id} className="claim-item">
                  <div className="claim-head">
                    <Avatar user={cr.claimant} size="sm" />
                    <strong>{cr.claimant.nickname || cr.claimant.username}</strong>
                    <span className="claim-time">{new Date(cr.created_at).toLocaleString("zh-CN")}</span>
                  </div>
                  {cr.reason && <div className="claim-reason">{cr.reason}</div>}
                  <div className="detail-row">
                    <button className="btn btn-primary btn-sm" onClick={() => handleApproveClaim(cr.id)} disabled={actionLoading}>批准</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => handleRejectClaim(cr.id)} disabled={actionLoading}>拒绝</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="card card-pad detail-section">
          <div className="section-head-row">
            <h3 className="section-h">附件 ({task.attachments.length})</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => fileInputRef.current?.click()}>+ 上传</button>
            <input ref={fileInputRef} type="file" onChange={handleFileUpload} style={{ display: "none" }} />
          </div>
          {task.attachments.length > 0 ? (
            <div className="att-list">
              {task.attachments.map((att) => (
                <div key={att.id} className="att-item">
                  <span className="att-icon">
                    {att.file_type === "image" ? "IMG" : att.file_type === "video" ? "VID" :
                     att.file_type === "document" ? "DOC" : att.file_type === "archive" ? "ZIP" : "FILE"}
                  </span>
                  <a href={att.file_url} target="_blank" rel="noopener noreferrer" className="att-name">{att.file_name}</a>
                  <span className="att-size">{formatSize(att.file_size)}</span>
                  <button className="att-del" onClick={() => handleDeleteAttachment(att.id)} title="删除">✕</button>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">暂无附件</p>
          )}
        </div>

        <div className="card card-pad detail-section">
          <h3 className="section-h">讨论 ({messages.length})</h3>
          {conversationId && (
            <div className="comment-input">
              <textarea className="textarea" value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="输入消息，使用 @用户名 提及他人..." rows={3} />
              <button className="btn btn-primary"
                      onClick={handleSendMessage}
                      disabled={!message.trim() || messageSubmitting}>
                {messageSubmitting ? "发送中…" : "发送"}
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
      </div>
    </AppShell>
  );
}
