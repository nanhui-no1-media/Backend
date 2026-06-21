function getCSRFToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

const BASE = "/tasks";

async function request(path: string, options: RequestInit = {}) {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
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

export const taskApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/tasks/${qs}`);
  },
  get: (id: number) => request(`/tasks/${id}/`),
  create: (data: object) => request("/tasks/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: object) => request(`/tasks/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) => request(`/tasks/${id}/`, { method: "DELETE" }),
  myTasks: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/tasks/my_tasks/${qs}`);
  },

  // Attachments
  addAttachment: (taskId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/tasks/${taskId}/add_attachment/`, { method: "POST", body: formData });
  },
  deleteAttachment: (taskId: number, attachmentId: number) =>
    request(`/tasks/${taskId}/delete_attachment/`, { method: "POST", body: JSON.stringify({ attachment_id: attachmentId }) }),

  // Assignment
  assign: (taskId: number, assigneeId: number | null) =>
    request(`/tasks/${taskId}/assign/`, { method: "POST", body: JSON.stringify({ assignee_id: assigneeId }) }),

  // Claim
  claim: (taskId: number, reason?: string) =>
    request(`/tasks/${taskId}/claim/`, { method: "POST", body: JSON.stringify({ reason }) }),
  approveClaim: (taskId: number, claimId: number) =>
    request(`/tasks/${taskId}/approve_claim/`, { method: "POST", body: JSON.stringify({ claim_id: claimId }) }),
  rejectClaim: (taskId: number, claimId: number) =>
    request(`/tasks/${taskId}/reject_claim/`, { method: "POST", body: JSON.stringify({ claim_id: claimId }) }),

  // Status
  complete: (taskId: number) =>
    request(`/tasks/${taskId}/complete/`, { method: "POST" }),
  cancel: (taskId: number) =>
    request(`/tasks/${taskId}/cancel/`, { method: "POST" }),
  approveCompletion: (taskId: number) =>
    request(`/tasks/${taskId}/approve_completion/`, { method: "POST" }),
  rejectCompletion: (taskId: number) =>
    request(`/tasks/${taskId}/reject_completion/`, { method: "POST" }),

  // Tags
  listTags: () => request("/tags/"),
  createTag: (data: { name: string; color?: string }) =>
    request("/tags/", { method: "POST", body: JSON.stringify(data) }),
};
