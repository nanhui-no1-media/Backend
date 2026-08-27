import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { messagingApi } from "../api/messaging";
import { onMessagingEvent, onMessagingOpen } from "../api/messagingSocket";
import { api } from "../api/client";
import type { TaskUser } from "../types/tasks";
import type { Conversation } from "../types/messaging";
import type { Paginated } from "../types/pagination";
import { usePagedList } from "../hooks/usePagedList";
import Pagination from "../components/Pagination";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";
import MessageThread from "../components/MessageThread";
import { useLoginModal } from "../components/LoginModalProvider";
import "../styles/messages.css";

const PAGE_SIZE = 20;

function preview(conv: Conversation): string {
  const last = conv.last_message;
  if (!last) return "暂无消息";
  if (last.retracted_at) return "该消息已撤回";
  return last.content?.slice(0, 40) || "暂无消息";
}

export default function MessagePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();
  const [user, setUser] = useState<TaskUser | null>(null);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);

  const { data: conversations, page, setPage, totalPages, loading: convLoading, refetch } = usePagedList<Conversation>(
    (params) => messagingApi.listConversations(params) as Promise<Paginated<Conversation>>,
    PAGE_SIZE,
  );

  useEffect(() => {
    document.title = "私信 · 传媒社";
  }, []);

  useEffect(() => {
    api.me()
      .then((d) => setUser({ ...d.user, avatar: d.profile.avatar, nickname: d.profile.nickname }))
      .catch(() => openLogin());
  }, [openLogin]);

  useEffect(() => {
    if (!id) return;
    messagingApi.getConversation(Number(id))
      .then((conv) => setActiveConv(conv))
      .catch(console.error);
  }, [id]);

  useEffect(() => {
    const refresh = () => {
      refetch();
      if (id) {
        messagingApi.getConversation(Number(id)).then(setActiveConv).catch(() => {});
      }
    };
    const offOpen = onMessagingOpen(refresh);
    const offEv = onMessagingEvent((ev) => {
      if (ev.event === "dm") refresh();
    });
    return () => { offOpen(); offEv(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const selectConversation = (conv: Conversation) => {
    setActiveConv(conv);
    navigate(`/messages/${conv.id}`, { replace: true });
  };

  const getConvTitle = (conv: Conversation) => {
    const other = conv.participants.find((p) => p.id !== user?.id);
    return other?.nickname || other?.username || conv.title || "私人会话";
  };

  const activeOther = activeConv?.participants.find((p) => p.id !== user?.id);

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>私信</span>
          </nav>
          <div className="page-head-row">
            <h1>私信</h1>
          </div>
        </div>
      </div>

      <div className="container">
        <div className="msg-layout">
          <div className="msg-side">
            <div className="msg-side-head">会话</div>
            <div className="msg-list">
              {convLoading ? (
                <div className="msg-list-empty">加载中…</div>
              ) : conversations.length === 0 ? (
                <div className="msg-list-empty">暂无私信</div>
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
                      </span>
                    </div>
                    <div className="ml-preview">{preview(conv)}</div>
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

          <div className="msg-thread">
            {activeConv ? (
              <>
                <div className="msg-thread-head">
                  {activeOther && <Link to={`/u/${activeOther.id}`}><Avatar user={activeOther} size="md" /></Link>}
                  <h3>{getConvTitle(activeConv)}</h3>
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
