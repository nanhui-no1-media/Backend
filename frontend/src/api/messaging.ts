import { createRequest } from "./shared";
import type { Message } from "../types/tasks";
import type { Paginated } from "../types/pagination";

const request = createRequest("/messaging");

export const messagingApi = {
  listConversations: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/conversations/${qs}`);
  },
  // 未读消息总数（驱动顶栏铃铛红点）；不含自己发出的消息。
  unreadCount: () => request(`/conversations/unread_count/`),
  getConversation: (id: number) => request(`/conversations/${id}/`),
  // 倒序分页（最新在前）：page=1 为最新一页，向上翻页拿更早。
  getMessages: (conversationId: number, page = 1) =>
    request(`/conversations/messages/?conversation_id=${conversationId}&page=${page}`) as Promise<Paginated<Message>>,
  sendMessage: (conversationId: number, content: string) =>
    request(`/conversations/${conversationId}/send_message/`, { method: "POST", body: JSON.stringify({ content }) }),
  markRead: (conversationId: number) =>
    request(`/conversations/${conversationId}/mark_read/`, { method: "POST" }),
  startPrivate: (userId: number) =>
    request("/conversations/start_private/", { method: "POST", body: JSON.stringify({ user_id: userId }) }),
  getTaskConversation: (taskId: number) =>
    request("/conversations/get_task_conversation/", { method: "POST", body: JSON.stringify({ task_id: taskId }) }),
  getProposalConversation: (proposalId: number) =>
    request("/conversations/get_proposal_conversation/", { method: "POST", body: JSON.stringify({ proposal_id: proposalId }) }),
};
