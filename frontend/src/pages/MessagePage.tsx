import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { messagingApi } from "../api/messaging";
import { api } from "../api/client";
import { Conversation, Message, TaskUser } from "../types/tasks";
import Avatar from "../components/Avatar";
import { useLoginModal } from "../components/LoginModalProvider";
import "./MessagePage.css";

export default function MessagePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();
  const [user, setUser] = useState<TaskUser | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const msgEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.me()
      .then((d) => setUser({ ...d.user, avatar: d.profile.avatar, nickname: d.profile.nickname }))
      .catch(() => openLogin());
  }, [navigate]);

  useEffect(() => {
    messagingApi.listConversations()
      .then((d) => {
        const list: Conversation[] = d.results || d;
        setConversations(list);
        // If URL has id, select that conversation
        if (id) {
          const conv = list.find((c) => c.id === Number(id));
          if (conv) selectConversation(conv);
        }
      })
      .catch(console.error);
  }, [id]);

  const selectConversation = async (conv: Conversation) => {
    setActiveConv(conv);
    navigate(`/messages/${conv.id}`, { replace: true });
    try {
      const msgs = await messagingApi.getMessages(conv.id);
      setMessages(msgs.results || msgs);
      messagingApi.markRead(conv.id).catch(() => {});
    } catch (err) {
      console.error(err);
    }
  };

  const handleSend = async () => {
    if (!activeConv || !input.trim()) return;
    setSending(true);
    try {
      const newMsg = await messagingApi.sendMessage(activeConv.id, input.trim());
      setMessages([...messages, newMsg]);
      setInput("");
    } catch (err: any) {
      console.error(err);
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    msgEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    <div className="msg-page">
      <div className="msg-container">
        {/* Sidebar */}
        <div className="msg-sidebar">
          <div className="msg-sidebar-header">
            <button className="task-back" onClick={() => navigate("/")}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
              </svg>
              返回
            </button>
            <h2 className="msg-sidebar-title">站内通信</h2>
          </div>
          <div className="msg-list">
            {conversations.length === 0 ? (
              <div className="msg-empty-sidebar">暂无会话</div>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  className={`msg-list-item${activeConv?.id === conv.id ? " active" : ""}`}
                  onClick={() => selectConversation(conv)}
                >
                  <div className="msg-list-title">{getConvTitle(conv)}</div>
                  <div className="msg-list-preview">
                    {conv.last_message?.content?.slice(0, 40) || "暂无消息"}
                  </div>
                  {conv.unread_count > 0 && (
                    <span className="msg-badge">{conv.unread_count}</span>
                  )}
                  <span className="msg-list-type">
                    {conv.conversation_type === "task" ? "任务" : "私信"}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Main */}
        <div className="msg-main">
          {activeConv ? (
            <>
              <div className="msg-main-header">
                {activeOther && <Avatar user={activeOther} size="md" />}
                <h3>{getConvTitle(activeConv)}</h3>
                <span className="msg-participant-count">
                  {activeConv.participants.length} 人
                </span>
              </div>
              <div className="msg-messages">
                {messages.length === 0 ? (
                  <div className="msg-empty-main">暂无消息，开始聊天吧</div>
                ) : (
                  messages.map((m) => (
                    <div
                      key={m.id}
                      className={`msg-bubble${m.sender.id === user?.id ? " mine" : ""}`}
                    >
                      {m.sender.id !== user?.id && (
                        <div className="msg-bubble-author user-with-avatar">
                          <Avatar user={m.sender} />
                          {m.sender.nickname || m.sender.username}
                        </div>
                      )}
                      <div className="msg-bubble-content">{m.content}</div>
                      <div className="msg-bubble-time">
                        {new Date(m.created_at).toLocaleString("zh-CN")}
                      </div>
                    </div>
                  ))
                )}
                <div ref={msgEndRef} />
              </div>
              <div className="msg-input-area">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="输入消息，@用户名 提及他人..."
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                />
                <button
                  className="task-btn-primary"
                  onClick={handleSend}
                  disabled={!input.trim() || sending}
                >
                  {sending ? "..." : "发送"}
                </button>
              </div>
            </>
          ) : (
            <div className="msg-empty-main">
              <p>选择一个会话开始聊天</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
