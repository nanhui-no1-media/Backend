import { useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useLoginModal } from "./LoginModalProvider";
import "./AppShell.css";

interface AppShellUser {
  id: number;
  username: string;
  email: string;
}
interface AppShellProfile {
  nickname?: string;
  avatar?: string | null;
}

const NAV: { label: string; path: string }[] = [
  { label: "主页", path: "/" },
  { label: "新闻", path: "/news" },
  { label: "活动申报", path: "/activity" },
  { label: "任务", path: "/tasks" },
];
const USER_MENU: { label: string; path: string }[] = [
  { label: "个人中心", path: "/profile" },
  { label: "任务管理", path: "/tasks" },
  { label: "活动申报", path: "/activity" },
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
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const userWrap = useRef<HTMLDivElement>(null);
  const bellWrap = useRef<HTMLDivElement>(null);
  const { openLogin, authNonce, notifyAuthChange } = useLoginModal();

  useEffect(() => {
    api.me()
      .then((d: any) => {
        setUser(d.user);
        setProfile(d.profile ?? {});
      })
      .catch(() => setUser(null));
  }, [authNonce]);

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
                <button className="bell" type="button" aria-label="站内通信"
                        aria-expanded={bellOpen} onClick={() => setBellOpen((v) => !v)}>
                  <BellIcon />
                  <span className="bell-dot" />
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
              <button className="sheet-item" type="button" onClick={() => go("/activity")}>活动申报</button>
              <button className="sheet-item" type="button" onClick={() => go("/messages")}>站内通信</button>
              <button className="sheet-item" type="button" onClick={logout}>退出登录</button>
            </>
          ) : (
            <button className="sheet-item" type="button" onClick={() => openLogin()}>登录</button>
          )}
        </div>
      </header>

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
              账户由信息组统一分发
            </p>
          </div>
          <div>
            <h5>栏目</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/"); }}>主页</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/news"); }}>新闻</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/activity"); }}>活动申报</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/tasks"); }}>任务</a>
          </div>
          <div>
            <h5>社团</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/"); }}>社团简介</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/"); }}>关于网站</a>
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
