// 各 api 模块共用的请求工具。
//
// CSRF 头、FormData 自动识别、204 空响应处理、统一的错误信息提取。
// 另外拦截 401 + reason=session_superseded（其他设备登录挤下线），
// 触发由 SessionGuard 注册的回调以弹出提示。

export interface SupersedeTakeover {
  device_name?: string;
  device_type?: string;
  ip?: string | null;
  time?: string;
}

type SupersedeHandler = (takeover: SupersedeTakeover) => void;

let supersedeHandler: SupersedeHandler | null = null;

export function setSupersedeHandler(fn: SupersedeHandler | null) {
  supersedeHandler = fn;
}

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
    if (res.status === 401 && data?.reason === "session_superseded") {
      // 被新设备挤下线：触发回调弹窗（幂等由 SessionGuard 保证），随后照常抛错
      supersedeHandler?.(data.takeover ?? {});
    }
    if (!res.ok) {
      const err = new Error(data.detail || data.error || "请求失败") as Error & {
        status: number;
        reason?: string;
        retry_after?: number;
      };
      err.status = res.status;
      err.reason = data?.reason;
      if (typeof data?.retry_after === "number") err.retry_after = data.retry_after;
      throw err;
    }
    return data as T;
  };
}
