import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { messagingApi } from "../api/messaging";
import { api } from "../api/client";
import { Conversation, TaskUser } from "../types/tasks";
import type { Paginated } from "../types/pagination";
import { usePagedList } from "../hooks/usePagedList";
import Pagination from "../components/Pagination";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";
import MessageThread from "../components/MessageThread";
import { useLoginModal } from "../components/LoginModalProvider";
import "../styles/messages.css";

const PAGE_SIZE = 20;

export default function MessagePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();
  const [user, setUser] = useState<TaskUser | null>(null);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);

  // 会话侧栏：-updated_at 排序（后端）+ 数字页码器（20/页）
  const { data: conversations, page, setPage, totalPages, loading: convLoading } = usePagedList<Conversation>(
    (params) => messagingApi.listConversations(params) as Promise<Paginated<Conversation>>,
    PAGE_SIZE,
  );

  useEffect(() => {
    api.me()
      .then((d) => setUser({ ...d.user, avatar: d.profile.avatar, nickname: d.profile.nickname }))
      .catch(() => openLogin());
  }, [openLogin]);

  // 直接带 URL id 进入：该会话可能不在当前页，单独拉详情激活
  useEffect(() => {
    if (!id) return;
    messagingApi.getConversation(Number(id))
      .then((conv) => setActiveConv(conv))
      .catch(console.error);
  }, [id]);

  const selectConversation = (conv: Conversation) => {
    setActiveConv(conv);
    navigate(`/messages/${conv.id}`, { replace: true });
  };

  const getConvTitle = (conv: Conversation) => {
    if (conv.conversation_type === "task") return conv.title || `任务讨论 #${conv.task}`;
    const other = conv.participants.find((p) => p.id !== user?.id);
    return other?.nickname || other?.username || "私人会话";
  };

  const activeOther =
    activeConv?.conversation_type === "private"
      ? activeConv.participants.find((p) => p.id !== user?.id)
      : undefined;

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>站内通信</span>
          </nav>
          <div className="page-head-row">
            <h1>站内通信</h1>
          </div>
        </div>
      </div>

      <div className="container">
        <div className="msg-layout">
          {/* 左：会话列表 */}
          <div className="msg-side">
            <div className="msg-side-head">会话</div>
            <div className="msg-list">
              {convLoading ? (
                <div className="msg-list-empty">加载中…</div>
              ) : conversations.length === 0 ? (
                <div className="msg-list-empty">暂无会话</div>
              ) : (
                conversations.map((conv) => (
                  <button
                    key={conv.id}
                    className={`msg-list-item${activeConv?.id === conv.id ? " active" : ""}`}
                    onClick={() => selectConversation(conv)}
                  >
                    <div className="ml-top">
                      <span className="ml-title">{getConvTitle(conv)}</span>
                      <span className="ml-meta">
                        {conv.unread_count > 0 && (
                          <span className="msg-badge">{conv.unread_count}</span>
                        )}
                        <span className="ml-type">
                          {conv.conversation_type === "task" ? "任务" : "私信"}
                        </span>
                      </span>
                    </div>
                    <div className="ml-preview">
                      {conv.last_message?.content?.slice(0, 40) || "暂无消息"}
                    </div>
                  </button>
                ))
              )}
            </div>
            {!convLoading && conversations.length > 0 && (
              <Pagination
                page={page}
                totalPages={totalPages}
                onChange={setPage}
                style={{ marginTop: "var(--s-2)", paddingBottom: "var(--s-3)" }}
              />
            )}
          </div>

          {/* 右：消息线程 */}
          <div className="msg-thread">
            {activeConv ? (
              <>
                <div className="msg-thread-head">
                  {activeOther && <Link to={`/u/${activeOther.id}`}><Avatar user={activeOther} size="md" /></Link>}
                  <h3>{getConvTitle(activeConv)}</h3>
                  <span className="mt-count">{activeConv.participants.length} 人</span>
                </div>
                {user && <MessageThread conversationId={activeConv.id} currentUser={user} />}
              </>
            ) : (
              <div className="msg-empty">选择一个会话开始聊天</div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
