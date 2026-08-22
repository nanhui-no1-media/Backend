import { createRequest } from "./shared";

const request = createRequest("/auth");

export const api = {
  login: (username: string, password: string) =>
    request("/login/", { method: "POST", body: JSON.stringify({ username, password }) }),

  loginWithEmail: (email: string, password: string) =>
    request("/login/", { method: "POST", body: JSON.stringify({ email, password }) }),

  logout: () =>
    request("/logout/", { method: "POST" }),

  me: () =>
    request("/me/"),

  verificationStatus: () =>
    request("/verification/"),

  verificationEmailBind: (email: string) =>
    request("/verification/email/bind/", { method: "POST", body: JSON.stringify({ email }) }),

  verificationManualSubmit: (data: FormData) =>
    request("/verification/manual/submit/", { method: "POST", body: data }),

  listSessions: () =>
    request("/sessions/"),

  getCsrf: () =>
    request("/csrf/"),

  register: (data: FormData) =>
    request("/register/", { method: "POST", body: data }),

  verifyEmail: (uid: string, token: string) =>
    request(`/verify-email/?uid=${encodeURIComponent(uid)}&token=${encodeURIComponent(token)}`),

  resendVerification: (email: string) =>
    request("/resend-verification/", { method: "POST", body: JSON.stringify({ email }) }),

  passwordReset: (email: string) =>
    request("/password-reset/", { method: "POST", body: JSON.stringify({ email }) }),

  passwordResetConfirm: (uid: string, token: string, new_password: string) =>
    request("/password-reset/confirm/", { method: "POST", body: JSON.stringify({ uid, token, new_password }) }),

  getProfile: () =>
    request("/profile/"),

  updateProfile: (data: FormData) =>
    request("/profile/update/", { method: "POST", body: data }),

  changePassword: (old_password: string, new_password: string) =>
    request("/profile/change-password/", { method: "POST", body: JSON.stringify({ old_password, new_password }) }),

  listUsers: () =>
    request("/users/"),

  // 用户搜索（任务表单指派/协作者）：分页信封 + ?search=（用户名/昵称模糊）
  searchUsers: (search: string) =>
    request(`/users/${search ? `?search=${encodeURIComponent(search)}` : ""}`) as Promise<{
      count: number;
      next: string | null;
      previous: string | null;
      results: { id: number; username: string; nickname: string; avatar: string | null }[];
    }>,

  getUserProfile: (id: number) =>
    request(`/users/${id}/profile/`),

  getUserContent: (id: number, type: "news" | "proposals" | "tasks", page = 1) =>
    request(`/users/${id}/content/?type=${type}&page=${page}`),

  inbox: () => request("/inbox/"),
};
