import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useLoginModal } from "../components/LoginModalProvider";
import MobileTabBar from "../components/MobileTabBar";
import "../styles/mobile.css";

interface MeUser {
  id: number;
  username: string;
  nickname?: string;
  avatar?: string | null;
  is_staff?: boolean;
  is_superuser?: boolean;
  identity_verified?: boolean;
}

const ENTRIES = [
  { to: "/profile", label: "个人资料" },
  { to: "/tasks", label: "我的任务" },
  { to: "/messages", label: "私信" },
  { to: "/feedback", label: "意见反馈" },
];

export default function MobileMePage() {
  const [user, setUser] = useState<MeUser | null>(null);
  const [loaded, setLoaded] = useState(false);
  const { openLogin } = useLoginModal();
  const navigate = useNavigate();
  useEffect(() => {
    document.title = "我的 · 南汇一中传媒社";
    api
      .me()
      .then((d: any) => setUser(d.user))
      .catch(() => setUser(null))
      .finally(() => setLoaded(true));
  }, []);

  const badge = user
    ? user.is_superuser
      ? "超级管理员"
      : user.is_staff
        ? "管理员"
        : user.identity_verified
          ? "认证用户"
          : "用户"
    : "";

  return (
    <div className="m-app">
      <header className="m-topbar">
        <div className="m-brand">我的</div>
      </header>

      <section className="m-me-card">
        {user ? (
          <>
            <img className="m-me-avatar" src={user.avatar || "/static/favicon.ico"} alt="" />
            <div>
              <div className="m-me-name">{user.nickname || user.username}</div>
              <div className="m-me-sub">
                @{user.username} · {badge}
              </div>
            </div>
          </>
        ) : (
          loaded && (
            <>
              <div className="m-me-name">未登录</div>
              <button className="m-me-login" onClick={() => openLogin()}>
                登录 / 注册
              </button>
            </>
          )
        )}
      </section>

      <div className="m-list">
        {ENTRIES.map((e) => (
          <div
            key={e.to}
            role="link"
            tabIndex={0}
            className="m-list-item"
            onClick={() => navigate(e.to)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter") navigate(e.to);
            }}
          >
            {e.label}
          </div>
        ))}
        {user && (user.is_staff || user.is_superuser) && (
          <div
            role="link"
            tabIndex={0}
            className="m-list-item"
            onClick={() => {
              window.location.href = "/admin/";
            }}
          >
            进入后台管理
          </div>
        )}
        {user && (
          <button
            className="m-list-item m-list-danger"
            onClick={() => {
              api.logout().then(() => window.location.reload());
            }}
          >
            退出登录
          </button>
        )}
      </div>

      <MobileTabBar />
    </div>
  );
}
