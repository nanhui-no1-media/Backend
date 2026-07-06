import { createRequest } from "./shared";

const request = createRequest("/messaging");

export const messagingApi = {
  listConversations: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/conversations/${qs}`);
  },
  getConversation: (id: number) => request(`/conversations/${id}/`),
  getMessages: (conversationId: number) =>
    request(`/conversations/messages/?conversation_id=${conversationId}`),
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
