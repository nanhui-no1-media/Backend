/**
 * Cloudflare Turnstile（自助注册人机校验）前端集成（#28）。
 *
 * sitekey 公开。生产部署时填入实际 sitekey（与后端 .env 的 TURNSTILE_SECRET_KEY 配对）；
 * 留空（本地开发默认）→ 不渲染挂件、不发送 token，后端在 DEBUG / 未配 secret 时跳过校验，
 * 便于不联网走通注册流程。
 *
 * api.js 由 template.html 以 <script async defer> 引入，挂载 window.turnstile。
 */
export const TURNSTILE_SITE_KEY = "";

/** 本地是否启用 Turnstile（配了 sitekey 才渲染挂件）。 */
export const isTurnstileEnabled = () => !!TURNSTILE_SITE_KEY;

export interface TurnstileRenderOptions {
  sitekey: string;
  callback?: (token: string) => void;
  "error-callback"?: () => void;
  "expired-callback"?: () => void;
  theme?: "light" | "dark" | "auto";
}

declare global {
  interface Window {
    turnstile?: {
      render: (container: HTMLElement, options: TurnstileRenderOptions) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId: string) => void;
    };
  }
}

/** 渲染挂件；返回 widgetId（用于 reset / remove）。window.turnstile 未就绪时返回 null。 */
export function renderTurnstile(
  container: HTMLElement,
  onToken: (token: string) => void,
  onError?: () => void
): string | null {
  const api = window.turnstile;
  if (!api || !TURNSTILE_SITE_KEY) return null;
  return api.render(container, {
    sitekey: TURNSTILE_SITE_KEY,
    callback: onToken,
    "error-callback": onError,
    "expired-callback": onError,
    theme: "auto",
  });
}
