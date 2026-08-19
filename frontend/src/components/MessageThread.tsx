import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { messagingApi } from "../api/messaging";
import { Message, TaskUser } from "../types/tasks";
import Avatar from "./Avatar";
import "../styles/messages.css";

/**
 * 共享消息线程：倒序分页（最新优先，向上加载更早）。
 * - conversationId 变化时重置并拉取最新一页；API 返回最新在前，展示时反转成从旧到新。
 * - 顶部「加载更早的消息」逐页向上翻；向上翻页时保持当前滚动位置。
 * - 自带输入框与发送；发送后追加到尾部并滚到底（autoScroll=false 时跳过，如任务详情讨论区）。
 * - 加载时顺手 markRead，清空该会话未读。
 */
export default function MessageThread({
  conversationId,
  currentUser,
  autoScroll = true,
  onCountChange,
}: {
  conversationId: number;
  currentUser: TaskUser;
  autoScroll?: boolean;
  onCountChange?: (count: number) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const countRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setMessages([]);
    setPage(1);
    messagingApi
      .getMessages(conversationId, 1)
      .then((d) => {
        if (cancelled) return;
        setMessages([...d.results].reverse()); // 最新在前 → 展示从旧到新
        setHasMore(d.next != null);
        countRef.current = d.count;
        onCountChange?.(d.count);
        if (autoScroll) listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
      })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false); });
    messagingApi.markRead(conversationId).catch(() => {});
    return () => { cancelled = true; };
    // conversationId 变化才重置线程；onCountChange/autoScroll 是稳定回调
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const loadEarlier = async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    const next = page + 1;
    const prevHeight = listRef.current?.scrollHeight ?? 0;
    try {
      const d = await messagingApi.getMessages(conversationId, next);
      setMessages((prev) => [...d.results].reverse().concat(prev));
      setPage(next);
      setHasMore(d.next != null);
      // 顶部追加后恢复原滚动位置，避免视觉跳动
      requestAnimationFrame(() => {
        const el = listRef.current;
        if (el) el.scrollTop = el.scrollHeight - prevHeight;
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    try {
      const m = await messagingApi.sendMessage(conversationId, input.trim());
      setMessages((prev) => [...prev, m]);
      setInput("");
      countRef.current += 1;
      onCountChange?.(countRef.current);
      if (autoScroll) listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    } catch (err) {
      console.error(err);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <div className="msg-bubbles" ref={listRef}>
        {loading ? (
          <div className="msg-empty">加载中…</div>
        ) : (
          <>
            {hasMore && (
              <button className="msg-load-more" onClick={loadEarlier} disabled={loadingMore}>
                {loadingMore ? "加载中…" : "加载更早的消息"}
              </button>
            )}
            {messages.length === 0 ? (
              <div className="msg-empty">暂无消息，开始聊天吧</div>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`msg-bubble${m.sender.id === currentUser.id ? " mine" : ""}`}
                >
                  {m.sender.id !== currentUser.id && (
                    <div className="mb-author">
                      <Link to={`/u/${m.sender.id}`}><Avatar user={m.sender} /></Link>
                      {m.sender.nickname || m.sender.username}
                    </div>
                  )}
                  <div className="mb-content">{m.content}</div>
                  <div className="mb-time">
                    {new Date(m.created_at).toLocaleString("zh-CN")}
                  </div>
                </div>
              ))
            )}
          </>
        )}
      </div>
      <div className="msg-input">
        <input
          className="input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入消息，@用户名 提及他人..."
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
        />
        <button className="btn btn-primary" onClick={handleSend} disabled={!input.trim() || sending}>
          {sending ? "..." : "发送"}
        </button>
      </div>
    </>
  );
}
