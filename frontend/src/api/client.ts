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

  getCsrf: () =>
    request("/csrf/"),

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
};
