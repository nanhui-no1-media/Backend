import { useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { messagingApi } from "../api/messaging";
import { useLoginModal } from "./LoginModalProvider";
import "./AppShell.css";

interface AppShellUser {
  id: number;
  username: string;
  email: string;
  permissions?: { can_review_content?: boolean };
}
interface AppShellProfile {
  nickname?: string;
  avatar?: string | null;
}
interface AppShellRole {
  variant?: string;
}

const NAV: { label: string; path: string }[] = [
  { label: "主页", path: "/" },
  { label: "新闻", path: "/news" },
  { label: "活动", path: "/activity" },
  { label: "反馈", path: "/feedback" },
  { label: "任务", path: "/tasks" },
];
const USER_MENU: { label: string; path: string }[] = [
  { label: "个人中心", path: "/profile" },
  { label: "任务管理", path: "/tasks" },
  { label: "活动", path: "/activity" },
  { label: "意见反馈", path: "/feedback" },
  { label: "后台管理", path: "/admin/" },
];

const BellIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z" />
    <path d="M10 19a2 2 0 0 0 4 0" />
  </svg>
);
const Caret = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9l6 6 6-6" />
  </svg>
);

export default function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<AppShellUser | null>(null);
  const [profile, setProfile] = useState<AppShellProfile>({});
  const [roleVariant, setRoleVariant] = useState<string>("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const userWrap = useRef<HTMLDivElement>(null);
  const bellWrap = useRef<HTMLDivElement>(null);
  const { openLogin, authNonce, notifyAuthChange } = useLoginModal();

  useEffect(() => {
    api.me()
      .then((d: any) => {
        setUser(d.user);
        setProfile(d.profile ?? {});
        setRoleVariant(d.role?.variant ?? "");
      })
      .catch(() => setUser(null));
  }, [authNonce]);

  // 铃铛红点：仅在「确有未读」时亮。登录态、跳转路由（含从 /messages 读毕返回）时刷新；
  // 不做轮询——校园门户按需刷新即可。失败则按 0 处理（红点隐去），不阻塞顶栏。
  useEffect(() => {
    if (!user) { setUnread(0); return; }
    messagingApi.unreadCount()
      .then((d: any) => setUnread(Number(d?.total) || 0))
      .catch(() => setUnread(0));
  }, [user, authNonce, location.pathname]);

  // 用 body.is-authed 驱动 cobalt 的 .act-guest/.act-user 显隐
  useEffect(() => {
    document.body.classList.toggle("is-authed", !!user);
    return () => { document.body.classList.remove("is-authed"); };
  }, [user]);

  // 点击外部关闭下拉
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (userWrap.current && !userWrap.current.contains(t)) setUserOpen(false);
      if (bellWrap.current && !bellWrap.current.contains(t)) setBellOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const go = (path: string) => {
    setDrawerOpen(false); setUserOpen(false); setBellOpen(false);
    if (path.startsWith("http") || path === "/admin/") window.location.href = path;
    else navigate(path);
  };
  const isActive = (p: string) =>
    p === "/" ? location.pathname === "/" : location.pathname.startsWith(p);
  const logout = async () => {
    setDrawerOpen(false); setUserOpen(false); setBellOpen(false);
    try { await api.logout(); } finally {
      // 通知认证态变化：同页（如首页）不重挂时，顶栏与本页 user 状态仍能立即刷新为游客
      notifyAuthChange();
      navigate("/");
    }
  };
  const name = profile.nickname || user?.username || "";
  const initial = (user?.username || "?").charAt(0).toUpperCase();

  return (
    <div className="cs appshell">
      <header className={"topnav" + (drawerOpen ? " is-open" : "")}>
        <div className="topnav-inner">
          <a className="topnav-brand" role="button" tabIndex={0} onClick={() => go("/")} aria-label="传媒社 首页">
            <img src="/static/favicon.ico" alt="传媒社社徽" />
            <span className="brand-name"><b>传媒社</b><span>南汇一中 · 2026</span></span>
          </a>
          <nav className="topnav-items" aria-label="主导航">
            {NAV.map((n) => (
              <a key={n.path} className="topnav-item" href="#"
                 aria-current={isActive(n.path) ? "page" : undefined}
                 onClick={(e) => { e.preventDefault(); go(n.path); }}>{n.label}</a>
            ))}
          </nav>
          <div className="topnav-actions">
            <div className="act-guest">
              <button className="btn btn-primary btn-sm" onClick={() => openLogin()}>登录</button>
            </div>
            <div className="act-user">
              <div className="bell-wrap" ref={bellWrap}>
                <button className="bell" type="button" aria-label={unread > 0 ? `站内通信，${unread} 条未读` : "站内通信"}
                        aria-expanded={bellOpen} onClick={() => setBellOpen((v) => !v)}>
                  <BellIcon />
                  {unread > 0 && <span className="bell-dot" />}
                </button>
                {bellOpen && (
                  <div className="bell-panel is-open" role="menu" aria-label="站内通信">
                    <div className="bell-head"><span>站内通信</span></div>
                    <a className="bell-foot" href="#"
                       onClick={(e) => { e.preventDefault(); go("/messages"); }}>查看全部站内通信</a>
                  </div>
                )}
              </div>
              <div className="user-chip-wrap" ref={userWrap}>
                <button className="user-chip" type="button" aria-expanded={userOpen}
                        onClick={() => setUserOpen((v) => !v)}>
                  <span className="avatar">{initial}</span>
                  <span className="uc-name">{name}</span>
                  <Caret className="uc-caret" />
                </button>
                {userOpen && (
                  <div className="user-menu is-open" role="menu">
                    <div className="um-head">
                      <span className="avatar lg">{initial}</span>
                      <div>
                        <div className="um-name">{name}</div>
                        <div className="um-sub">@{user?.username}</div>
                      </div>
                    </div>
                    {USER_MENU.map((m) => (
                      <button key={m.path} className="user-menu-item" type="button" onClick={() => go(m.path)}>
                        {m.label}
                      </button>
                    ))}
                    {user?.permissions?.can_review_content && (
                      <button className="user-menu-item" type="button" onClick={() => go("/reviews")}>
                        审核队列
                      </button>
                    )}
                    <div className="um-sep" />
                    <button className="user-menu-item danger" type="button" onClick={logout}>退出登录</button>
                  </div>
                )}
              </div>
            </div>
            <button className="topnav-toggle" type="button" aria-label="打开菜单"
                    aria-expanded={drawerOpen} onClick={() => setDrawerOpen((v) => !v)}>
              <span />
            </button>
          </div>
        </div>

        <div className="mobile-sheet">
          {NAV.map((n) => (
            <a key={n.path} className={isActive(n.path) ? "active" : ""} href="#"
               onClick={(e) => { e.preventDefault(); go(n.path); }}>{n.label}</a>
          ))}
          <div className="sheet-sep" />
          {user ? (
            <>
              <button className="sheet-item" type="button" onClick={() => go("/profile")}>个人中心</button>
              <button className="sheet-item" type="button" onClick={() => go("/tasks")}>任务管理</button>
              <button className="sheet-item" type="button" onClick={() => go("/activity")}>活动</button>
              <button className="sheet-item" type="button" onClick={() => go("/feedback")}>意见反馈</button>
              {user.permissions?.can_review_content && (
                <button className="sheet-item" type="button" onClick={() => go("/reviews")}>审核队列</button>
              )}
              <button className="sheet-item" type="button" onClick={() => go("/messages")}>站内通信</button>
              <button className="sheet-item" type="button" onClick={logout}>退出登录</button>
            </>
          ) : (
            <button className="sheet-item" type="button" onClick={() => openLogin()}>登录</button>
          )}
        </div>
      </header>

      {/* 未验证提示（ADR-0006 / ADR-0005）：仅访客（未验证普通成员）提示，超管 / 管理员 /
          已验证用户不打扰。点击去验证面板。 */}
      {user && roleVariant === "visitor" && (
        <button className="identity-banner" type="button" role="status"
                onClick={() => go("/profile?tab=verification")}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8h.01M11 12h1v4h1" /></svg>
          <span>你的账号尚未验证，发帖 / 发消息 / 建申报暂不可用。前往「账号验证」完成验证。</span>
        </button>
      )}

      <main className="page">{children}</main>

      <footer className="footer">
        <div className="footer-inner">
          <div>
            <div className="footer-brand">
              <img src="/static/favicon.ico" alt="传媒社社徽" />
              <b>传媒社</b>
            </div>
            <p className="footer-note">
              上海市南汇第一中学 · 传媒社<br />
              校园影像与新媒体作品策展门户<br />
              自助注册 · 信息组核审
            </p>
          </div>
          <div>
            <h5>栏目</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/"); }}>主页</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/news"); }}>新闻</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/activity"); }}>活动</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/feedback"); }}>反馈</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/tasks"); }}>任务</a>
          </div>
          <div>
            <h5>关于</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/about"); }}>关于我们</a>
          </div>
          <div>
            <h5>账户</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); openLogin(); }}>登录</a>
          </div>
        </div>
        <div className="footer-bottom tnum">© 2026 上海市南汇第一中学 · 传媒社 · 信息组</div>
      </footer>
    </div>
  );
}
