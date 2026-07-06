// 各 api 模块共用的请求工具。
//
// 每个 api 模块（client / tasks / messaging / proposals）原先各自复制了一份
// getCSRFToken + request 样板。这里抽出统一的实现：CSRF 头、FormData 自动识别、
// 204 空响应处理、统一的错误信息提取。
//
// 用法：const request = createRequest("/tasks");  → 绑定到各自前缀的请求函数。

export function getCSRFToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function createRequest(base: string) {
  return async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
    const isFormData = options.body instanceof FormData;
    const res = await fetch(`${base}${path}`, {
      ...options,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        "X-CSRFToken": getCSRFToken(),
        ...options.headers,
      },
      credentials: "include",
    });
    if (res.status === 204) return null as T;
    const data = await res.json();
    if (!res.ok) {
      const err = new Error(data.detail || data.error || "请求失败") as Error & { status: number };
      err.status = res.status;
      throw err;
    }
    return data as T;
  };
}
