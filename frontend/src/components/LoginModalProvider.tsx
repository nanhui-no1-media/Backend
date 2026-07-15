import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import LoginModal from "./LoginModal";

interface LoginModalCtx {
  openLogin: (redirectTo?: string) => void;
  closeLogin: () => void;
  /** 每次成功登录后自增；受保护路由可依赖它重新校验会话。 */
  loginNonce: number;
}

const Ctx = createContext<LoginModalCtx | null>(null);

export function useLoginModal(): LoginModalCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLoginModal 必须在 <LoginModalProvider> 内使用");
  return v;
}

/**
 * 全局登录弹窗 Provider：挂在 <HashRouter> 内、<SessionGuard> 外，
 * 使顶栏 / 受保护路由 / 各「去登录」入口都能调用 openLogin()。
 * 渲染时机：始终挂载 <LoginModal>，由其内部据 open 决定显隐。
 */
export default function LoginModalProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [redirectTo, setRedirectTo] = useState<string | undefined>(undefined);
  const [loginNonce, setLoginNonce] = useState(0);

  const openLogin = useCallback((to?: string) => {
    setRedirectTo(to);
    setOpen(true);
  }, []);
  const closeLogin = useCallback(() => setOpen(false), []);
  const onLoggedIn = useCallback(() => setLoginNonce((n) => n + 1), []);

  return (
    <Ctx.Provider value={{ openLogin, closeLogin, loginNonce }}>
      {children}
      <LoginModal open={open} redirectTo={redirectTo} onClose={closeLogin} onLoggedIn={onLoggedIn} />
    </Ctx.Provider>
  );
}
