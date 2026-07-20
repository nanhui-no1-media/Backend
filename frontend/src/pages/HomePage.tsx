import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { newsApi } from "../api/news";
import AppShell from "../components/AppShell";
import ClubFeed from "../components/ClubFeed";
import { useLoginModal } from "../components/LoginModalProvider";
import "../styles/home.css";

interface User {
  id: number;
  username: string;
}


const EqBars = () => (
  <span className="eq" aria-hidden="true"><span /><span /><span /><span /></span>
);

export default function HomePage() {
  const [user, setUser] = useState<User | null>(null);
  const [overview, setOverview] = useState<{ members: number; works: number } | null>(null);
  const navigate = useNavigate();
  const { openLogin, authNonce } = useLoginModal();

  useEffect(() => {
    document.title = "南汇一中 · 传媒社";
    api.me()
      .then((data) => setUser({ id: data.user.id, username: data.user.username }))
      .catch(() => setUser(null));
  }, [authNonce]);

  // 社团概览统计：匿名可读，与登录态无关，挂载时拉一次
  useEffect(() => {
    newsApi.overview()
      .then(setOverview)
      .catch(() => setOverview(null));
  }, []);

  // 受保护目的地：游客改走登录弹窗（带 redirectTo）
  const go = (path: string) => {
    if (user) navigate(path);
    else openLogin(path);
  };

  return (
    <AppShell>
      {/* ── Hero ── */}
      <section className="hero">
        <div className="hero-inner">
          <span className="hero-badge"><EqBars /> 上海市南汇第一中学 · 传媒社</span>
          <h1>用镜头记录青春<br /><span className="accent">用设计诠释创意</span></h1>
          <p className="hero-sub">校园影像、短视频与新媒体作品的策展窗口；社团动态、活动申报与站内通信，一站式直达。</p>
          <div className="hero-actions">
            <button className="btn btn-primary btn-lg" type="button" onClick={() => go("/activity")}>
              加入社团
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </button>
            <button className="btn btn-ghost btn-lg" type="button" onClick={() => navigate("/activity")}>浏览动态</button>
          </div>
          <div className="quick-strip">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16v12H7l-3 3z" /></svg> 活动申报
            </a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/tasks"); }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l2 2 4-4" /><rect x="4" y="5" width="16" height="16" rx="2" /><path d="M9 3v4M15 3v4" /></svg> 任务
            </a>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2l2.4 6.9H22l-6 4.4 2.3 7L12 16l-6.3 4.3L8 13.3 2 8.9h7.6z" /></svg> 建议提交
            </a>
          </div>
        </div>
      </section>

      {/* ── 两栏主体 ── */}
      <div className="container">
        <div className="home-grid">
          {/* 左：看板娘栏 + 社团概览 */}
          <aside className="mascot-rail">
            <div className="mascot-frame">
              <div className="mascot-note">
                <b>看板娘立绘区</b>
                Live2D 立绘待接入
              </div>
            </div>
            <div className="rail-card">
              <h4><span className="bar" /> 社团概览</h4>
              <div className="stat-row"><span className="k">成立</span><span className="v tnum">2026.03</span></div>
              <div className="stat-row"><span className="k">成员</span><span className="v tnum">{overview ? overview.members : "—"}</span></div>
              <div className="stat-row"><span className="k">指导</span><span className="v">信息组</span></div>
              <div className="stat-row"><span className="k">作品</span><span className="v tnum">{overview ? overview.works : "—"}</span></div>
            </div>
            <div className="rail-card rail-actions">
              <h4><span className="bar" /> 快速入口</h4>
              <button className="btn btn-secondary btn-sm" type="button" onClick={() => go("/activity/new")}>提交活动申报</button>
              <button className="btn btn-ghost btn-sm" type="button" onClick={() => go("/tasks")}>我的任务</button>
              <button className="btn btn-ghost btn-sm" type="button" onClick={() => navigate("/activity")}>浏览活动申报</button>
            </div>
          </aside>

          {/* 右：社团动态 */}
          <div className="home-main">
            <ClubFeed user={user} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
