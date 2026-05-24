import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "../api/client";
import "./HomePage.css";

interface User {
  id: number;
  username: string;
  email: string;
  avatar?: string | null;
  nickname?: string;
}

interface Activity {
  id: number;
  title: string;
  date: string;
  category: string;
  status: "进行中" | "已结束" | "即将开始";
  emoji: string;
  gradient: string;
}

const NAV_ITEMS = [
  { label: "主页", path: "/", protected: false },
  { label: "社团简介", path: "/about", protected: false },
  { label: "组织架构", path: "/organization", protected: false },
  { label: "任务管理", path: "/tasks", protected: true },
  { label: "站内通信", path: "/messages", protected: true },
  { label: "活动申报", path: "/activity", protected: true },
  { label: "社团管理", path: "/manage", protected: true },
  { label: "后台管理", path: "/admin/", protected: true },
];

const ACTIVITIES: Activity[] = [
  { id: 1, title: "2024年度校园摄影大赛作品征集", date: "2024-03-15", category: "比赛", status: "进行中", emoji: "📷", gradient: "linear-gradient(135deg, #667eea, #764ba2)" },
  { id: 2, title: "短视频制作技能培训课程", date: "2024-03-10", category: "培训", status: "已结束", emoji: "🎬", gradient: "linear-gradient(135deg, #f093fb, #f5576c)" },
  { id: 3, title: "校园文化节宣传片拍摄", date: "2024-03-08", category: "项目", status: "进行中", emoji: "🎥", gradient: "linear-gradient(135deg, #4facfe, #00f2fe)" },
  { id: 4, title: "社团新学期成员见面会", date: "2024-03-01", category: "活动", status: "已结束", emoji: "🎉", gradient: "linear-gradient(135deg, #43e97b, #38f9d7)" },
  { id: 5, title: "Adobe 设计软件入门讲座", date: "2024-02-25", category: "培训", status: "已结束", emoji: "🎨", gradient: "linear-gradient(135deg, #fa709a, #fee140)" },
  { id: 6, title: "校园新闻采编实务培训", date: "2024-02-20", category: "培训", status: "已结束", emoji: "📰", gradient: "linear-gradient(135deg, #a18cd1, #fbc2eb)" },
  { id: 7, title: "社团 Logo 设计征集活动", date: "2024-02-15", category: "比赛", status: "已结束", emoji: "✏️", gradient: "linear-gradient(135deg, #fccb90, #d57eeb)" },
  { id: 8, title: "新媒体运营实战分享会", date: "2024-02-10", category: "分享", status: "已结束", emoji: "💡", gradient: "linear-gradient(135deg, #e0c3fc, #8ec5fc)" },
];

const LockSvg = () => (
  <svg className="lock-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

export default function HomePage() {
  const [user, setUser] = useState<User | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    document.title = "南汇一中传媒设";
    api.me()
      .then((data) => setUser({ ...data.user, avatar: data.profile.avatar, nickname: data.profile.nickname }))
      .catch(() => setUser(null));
  }, []);

  const handleNav = (item: (typeof NAV_ITEMS)[number]) => {
    setMenuOpen(false);
    if (item.protected && !user) {
      navigate("/login");
      return;
    }
    if (item.path.startsWith("http") || item.path.endsWith("/")) {
      window.location.href = item.path;
    } else {
      navigate(item.path);
    }
  };

  const handleLogout = async () => {
    try { await api.logout(); } finally { navigate("/login"); }
  };

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <div className="home-page">
      {/* ── Navigation ── */}
      <nav className="main-nav">
        <div className="nav-inner">
          <div className="nav-brand" onClick={() => navigate("/")} role="button" tabIndex={0}>
            <img src="/static/favicon.ico" alt="" className="nav-logo" />
            <span className="nav-title">南汇一中传媒设</span>
          </div>

          <div className="nav-center">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.label}
                className={[
                  "nav-link",
                  isActive(item.path) ? "active" : "",
                  item.protected ? "is-protected" : "",
                  user ? "logged-in" : "",
                ].filter(Boolean).join(" ")}
                onClick={() => handleNav(item)}
              >
                {item.label}
                {item.protected && <LockSvg />}
              </button>
            ))}
          </div>

          <div className="nav-right">
            {user ? (
              <>
                <div className="user-info" onClick={() => navigate("/profile")} role="button" tabIndex={0}>
                  <div className="user-avatar">
                    {user.avatar ? <img src={user.avatar} alt="" /> : user.username.charAt(0).toUpperCase()}
                  </div>
                  <span className="user-name">{user.nickname || user.username}</span>
                </div>
                <button className="btn-logout" onClick={handleLogout}>退出</button>
              </>
            ) : (
              <button className="btn-login" onClick={() => navigate("/login")}>登录</button>
            )}
          </div>

          <button className="mobile-toggle" onClick={() => setMenuOpen((v) => !v)} aria-label="菜单">
            <span className={`hamburger${menuOpen ? " open" : ""}`} />
          </button>
        </div>

        {menuOpen && (
          <div className="mobile-menu">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.label}
                className={`mobile-nav-link${isActive(item.path) ? " active" : ""}`}
                onClick={() => handleNav(item)}
              >
                {item.label}
                {item.protected && !user && " 🔒"}
              </button>
            ))}
            <div className="mobile-menu-divider" />
            {user ? (
              <>
                <button className="mobile-nav-link" onClick={() => { setMenuOpen(false); navigate("/profile"); }}>个人中心</button>
                <button className="mobile-nav-link" onClick={() => { setMenuOpen(false); handleLogout(); }}>退出登录</button>
              </>
            ) : (
              <button className="mobile-nav-link" onClick={() => { setMenuOpen(false); navigate("/login"); }}>登录</button>
            )}
          </div>
        )}
      </nav>

      {/* ── Hero ── */}
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-badge">传媒设</div>
          <h1 className="hero-title">南汇一中传媒设</h1>
          <p className="hero-subtitle">用镜头记录青春，用设计诠释创意</p>
          <div className="hero-actions">
            <button className="hero-btn hero-btn-primary" onClick={() => handleNav(NAV_ITEMS[1])}>了解我们</button>
            <button className="hero-btn hero-btn-ghost" onClick={() => { if (!user) navigate("/login"); }}>加入社团</button>
          </div>
        </div>
      </section>

      {/* ── Activities ── */}
      <section className="section">
        <div className="section-header">
          <h2 className="section-title">社团动态</h2>
        </div>
        <div className="activity-grid">
          {ACTIVITIES.map((item) => (
            <div key={item.id} className="activity-card">
              <div className="card-cover" style={{ background: item.gradient }}>
                <span className="card-emoji">{item.emoji}</span>
              </div>
              <div className="card-body">
                <span className="card-tag" data-status={item.status}>{item.status}</span>
                <div className="card-title">{item.title}</div>
                <div className="card-meta">
                  <span className="card-date">{item.date}</span>
                  <span className="card-category">{item.category}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
