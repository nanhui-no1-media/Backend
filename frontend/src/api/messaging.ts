function getCSRFToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

const BASE = "/messaging";

async function request(path: string, options: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken(),
      ...options.headers,
    },
    credentials: "include",
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || "请求失败");
  }
  return data;
}

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
};
