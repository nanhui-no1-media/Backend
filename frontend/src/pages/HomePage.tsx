import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { newsApi } from "../api/news";
import AppShell from "../components/AppShell";
import { useLoginModal } from "../components/LoginModalProvider";
import "../styles/home.css";

interface User {
  id: number;
  username: string;
}

interface Activity {
  id: number;
  title: string;
  date: string;
  category: string;
  status: "进行中" | "已结束" | "即将开始";
  emoji: string;
}

// 社团动态（mock 占位，真实数据接入记为后续债）
const ACTIVITIES: Activity[] = [
  { id: 1, title: "2024 年度校园摄影大赛作品征集", date: "2024.03.15", category: "比赛", status: "进行中", emoji: "📷" },
  { id: 2, title: "短视频制作技能培训课程", date: "2024.03.10", category: "培训", status: "已结束", emoji: "🎬" },
  { id: 3, title: "校园文化节宣传片拍摄", date: "2024.03.08", category: "项目", status: "进行中", emoji: "🎥" },
  { id: 4, title: "社团新学期成员见面会", date: "2024.03.01", category: "活动", status: "已结束", emoji: "🎉" },
  { id: 5, title: "Adobe 设计软件入门讲座", date: "2024.02.25", category: "培训", status: "已结束", emoji: "🎨" },
  { id: 6, title: "新媒体运营实战分享会", date: "2024.02.10", category: "分享", status: "已结束", emoji: "💡" },
];

const STATUS_BADGE: Record<Activity["status"], string> = {
  "进行中": "badge-success",
  "即将开始": "badge-warning",
  "已结束": "badge-neutral",
};

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
            <section>
              <div className="section-head">
                <div>
                  <div className="eyebrow">CLUB · ACTIVITY</div>
                  <h2 className="section-title"><span className="bar" /> 社团动态</h2>
                </div>
                <a className="section-link" href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>
                  全部动态
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
                </a>
              </div>
              <div className="activity-grid">
                {ACTIVITIES.map((item) => (
                  <a key={item.id} className="card card-hover activity-card" href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>
                    <div className="card-media ph-img card-cover">
                      <span className={"badge badge-brand cat"}>{item.category}</span>
                      <span className="cover-emoji">{item.emoji}</span>
                    </div>
                    <div className="card-body">
                      <span className={"badge " + STATUS_BADGE[item.status]}><span className="badge-dot" />{item.status}</span>
                      <h3>{item.title}</h3>
                      <div className="card-foot"><span className="date tnum">{item.date}</span><span className="muted">{item.category}</span></div>
                    </div>
                  </a>
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
