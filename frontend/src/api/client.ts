const API_BASE = "/auth";

function getCSRFToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function request(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken(),
      ...options.headers,
    },
    credentials: "include",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

export const api = {
  login: (username: string, password: string) =>
    request("/login/", { method: "POST", body: JSON.stringify({ username, password }) }),

  loginWithEmail: (email: string, password: string) =>
    request("/login/", { method: "POST", body: JSON.stringify({ email, password }) }),

  logout: () =>
    request("/logout/", { method: "POST" }),

  me: () =>
    request("/me/"),

  passwordReset: (email: string) =>
    request("/password-reset/", { method: "POST", body: JSON.stringify({ email }) }),

  passwordResetConfirm: (uid: string, token: string, new_password: string) =>
    request("/password-reset/confirm/", { method: "POST", body: JSON.stringify({ uid, token, new_password }) }),
};
