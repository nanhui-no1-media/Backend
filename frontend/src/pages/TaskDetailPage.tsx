import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { taskApi } from "../api/tasks";
import { messagingApi } from "../api/messaging";
import { api } from "../api/client";
import {
  TaskDetail, Message,
  STATUS_LABELS, PRIORITY_LABELS, PRIORITY_COLORS, STATUS_COLORS,
} from "../types/tasks";
import RichTextEditor from "../components/RichTextEditor";
import "./TaskDetailPage.css";

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
  const [currentUser, setCurrentUser] = useState<{ id: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.me().then((d) => setCurrentUser({ id: d.user.id })).catch(() => {});
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
    setActionLoading(true);
    try {
      const updated = await taskApi.rejectCompletion(task.id);
      setTask(updated);
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
  const isAssignee = task && currentUser && task.assignee?.id === currentUser.id;
  const canClaim = task && !task.assignee && currentUser && task.creator.id !== currentUser.id && task.status === "pending";
  const canComplete = task && task.status === "in_progress" && !!isAssignee;
  const canReviewCompletion = task && task.status === "reviewing" && !!isCreator;
  const canCancel = task && task.status !== "completed" && task.status !== "cancelled" && isCreator;
  const pendingClaims = task?.claim_requests.filter((c) => c.status === "pending") || [];

  if (loading) return <div className="task-page"><div className="task-loading">加载中...</div></div>;
  if (error && !task) return <div className="task-page"><div className="task-loading">{error}</div></div>;
  if (!task) return <div className="task-page"><div className="task-loading">任务不存在</div></div>;

  return (
    <div className="task-page">
      <div className="task-detail-container">
        <div className="task-detail-header">
          <button className="task-back" onClick={() => navigate("/tasks")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
            </svg>
            任务列表
          </button>
          {task.status === "pending" && (
            <button className="task-btn-secondary" onClick={() => navigate(`/tasks/${task.id}/edit`)}>
              编辑
            </button>
          )}
        </div>

        {error && <div className="task-error">{error}</div>}

        <div className="task-detail-title-row">
          <h1 className="task-detail-title">{task.title}</h1>
          <span
            className="task-status-badge"
            style={{
              backgroundColor: STATUS_COLORS[task.status] + "18",
              color: STATUS_COLORS[task.status],
              fontSize: "14px",
              padding: "6px 14px",
              borderRadius: "8px",
              fontWeight: 600,
            }}
          >
            {STATUS_LABELS[task.status]}
          </span>
        </div>

        <div className="task-detail-meta">
          <div className="meta-item">
            <span className="meta-label">优先级</span>
            <span style={{ color: PRIORITY_COLORS[task.priority] }}>{PRIORITY_LABELS[task.priority]}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">创建人</span>
            <span>{task.creator.nickname || task.creator.username}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">负责人</span>
            <span>{task.assignee?.nickname || task.assignee?.username || "未分配"}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">创建时间</span>
            <span>{new Date(task.created_at).toLocaleString("zh-CN")}</span>
          </div>
        </div>

        {/* Action buttons */}
        {(canComplete || canReviewCompletion || canCancel) && (
          <div className="task-actions-row">
            {canComplete && (
              <button className="task-btn-primary" onClick={handleComplete} disabled={actionLoading}>
                {actionLoading ? "处理中..." : "提交验收"}
              </button>
            )}
            {canReviewCompletion && (
              <>
                <button className="task-btn-primary" onClick={handleApproveCompletion} disabled={actionLoading}>
                  {actionLoading ? "处理中..." : "通过验收"}
                </button>
                <button className="task-btn-cancel" onClick={handleRejectCompletion} disabled={actionLoading}>
                  打回
                </button>
              </>
            )}
            {canCancel && (
              <button className="task-btn-cancel" onClick={handleCancel} disabled={actionLoading}>
                取消任务
              </button>
            )}
          </div>
        )}

        {task.tags.length > 0 && (
          <div className="task-detail-tags">
            {task.tags.map((t) => (
              <span key={t.id} className="task-tag" style={{ backgroundColor: t.color + "18", color: t.color }}>
                {t.name}
              </span>
            ))}
          </div>
        )}

        {task.collaborators.length > 0 && (
          <div className="task-detail-section">
            <h3>协作者</h3>
            <div className="collaborator-list">
              {task.collaborators.map((u) => (
                <span key={u.id} className="collaborator-chip">
                  {u.nickname || u.username}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="task-detail-section">
          <h3>描述</h3>
          <div className="task-description">
            {task.description ? (
              <RichTextEditor content={task.description} editable={false} />
            ) : (
              <p className="task-empty-text">暂无描述</p>
            )}
          </div>
        </div>

        {canClaim && (
          <div className="task-detail-section">
            <h3>认领任务</h3>
            <div className="claim-form">
              <textarea
                value={claimReason}
                onChange={(e) => setClaimReason(e.target.value)}
                placeholder="说明你想认领此任务的理由..."
                rows={2}
              />
              <button className="task-btn-primary" onClick={handleClaim} disabled={claiming}>
                {claiming ? "提交中..." : "申请认领"}
              </button>
            </div>
          </div>
        )}

        {isCreator && pendingClaims.length > 0 && (
          <div className="task-detail-section">
            <h3>认领请求 ({pendingClaims.length})</h3>
            <div className="claim-list">
              {pendingClaims.map((cr) => (
                <div key={cr.id} className="claim-item">
                  <div className="claim-header">
                    <strong>{cr.claimant.nickname || cr.claimant.username}</strong>
                    <span className="claim-time">{new Date(cr.created_at).toLocaleString("zh-CN")}</span>
                  </div>
                  {cr.reason && <div className="claim-reason">{cr.reason}</div>}
                  <div className="claim-actions">
                    <button className="task-btn-primary task-btn-sm" onClick={() => handleApproveClaim(cr.id)} disabled={actionLoading}>
                      批准
                    </button>
                    <button className="task-btn-secondary task-btn-sm" onClick={() => handleRejectClaim(cr.id)} disabled={actionLoading}>
                      拒绝
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="task-detail-section">
          <div className="section-header">
            <h3>附件 ({task.attachments.length})</h3>
            <button className="task-btn-sm" onClick={() => fileInputRef.current?.click()}>
              + 上传
            </button>
            <input ref={fileInputRef} type="file" onChange={handleFileUpload} style={{ display: "none" }} />
          </div>
          {task.attachments.length > 0 ? (
            <div className="attachment-list">
              {task.attachments.map((att) => (
                <div key={att.id} className="attachment-item">
                  <span className={`attachment-icon att-${att.file_type}`}>
                    {att.file_type === "image" ? "IMG" :
                     att.file_type === "video" ? "VID" :
                     att.file_type === "document" ? "DOC" :
                     att.file_type === "archive" ? "ZIP" : "FILE"}
                  </span>
                  <a href={att.file_url} target="_blank" rel="noopener noreferrer" className="attachment-name">
                    {att.file_name}
                  </a>
                  <span className="attachment-size">{formatSize(att.file_size)}</span>
                  <button className="attachment-delete" onClick={() => handleDeleteAttachment(att.id)} title="删除">x</button>
                </div>
              ))}
            </div>
          ) : (
            <p className="task-empty-text">暂无附件</p>
          )}
        </div>

        <div className="task-detail-section">
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
                className="task-btn-primary"
                onClick={handleSendMessage}
                disabled={!message.trim() || messageSubmitting}
              >
                {messageSubmitting ? "发送中..." : "发送"}
              </button>
            </div>
          )}
          {messages.length > 0 ? (
            <div className="comment-list">
              {messages.map((m) => (
                <div key={m.id} className="comment-item">
                  <div className="comment-header">
                    <strong>{m.sender.nickname || m.sender.username}</strong>
                    <span className="comment-time">{new Date(m.created_at).toLocaleString("zh-CN")}</span>
                  </div>
                  <div className="comment-content">{m.content}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="task-empty-text">暂无讨论</p>
          )}
        </div>
      </div>
    </div>
  );
}
