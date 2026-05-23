import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import "./HomePage.css";

interface User {
  id: number;
  username: string;
  email: string;
  avatar?: string | null;
  nickname?: string;
}

interface ContentItem {
  id: number;
  title: string;
  author: string;
  views: string;
  duration: string;
  emoji: string;
  badge?: { text: string; color: string };
}

const MOCK_CONTENT: ContentItem[] = [
  { id: 1, title: "深入理解现代前端架构设计原则与实践", author: "技术先锋", views: "12.3万", duration: "15:42", emoji: "🖥️", badge: { text: "热门", color: "#FB7299" } },
  { id: 2, title: "Python 全栈开发实战教程 Day 1", author: "代码学院", views: "8.7万", duration: "23:18", emoji: "🐍", badge: { text: "最新", color: "#23ADE5" } },
  { id: 3, title: "这个算法题 99% 的人都会做错", author: "算法竞赛圈", views: "45.1万", duration: "08:33", emoji: "🧮" },
  { id: 4, title: "从零搭建一个高性能分布式系统", author: "架构师日记", views: "6.2万", duration: "31:05", emoji: "🏗️" },
  { id: 5, title: "React 19 新特性全面解析", author: "前端观察", views: "19.8万", duration: "12:47", emoji: "⚛️", badge: { text: "精选", color: "#FF6633" } },
  { id: 6, title: "Linux 内核探秘：进程调度的秘密", author: "极客时间", views: "3.4万", duration: "18:22", emoji: "🐧" },
  { id: 7, title: "手把手教你设计一个优秀的数据库", author: "DBA之路", views: "7.9万", duration: "27:14", emoji: "🗄️" },
  { id: 8, title: "机器学习入门到放弃再到入门", author: "AI实验室", views: "33.6万", duration: "45:00", emoji: "🤖", badge: { text: "热门", color: "#FB7299" } },
  { id: 9, title: "用 Rust 重写一切：WebAssembly 篇", author: "锈迹斑斑", views: "5.1万", duration: "20:38", emoji: "🦀" },
  { id: 10, title: "设计模式之美：观察者模式详解", author: "代码之美", views: "4.3万", duration: "09:56", emoji: "🎨" },
  { id: 11, title: "Docker 容器化部署最佳实践", author: "运维老司机", views: "11.2万", duration: "16:30", emoji: "🐳" },
  { id: 12, title: "TypeScript 类型体操入门指南", author: "类型安全", views: "21.7万", duration: "14:15", emoji: "📐", badge: { text: "精选", color: "#FF6633" } },
  { id: 13, title: "计算机网络：从原理到实践", author: "网络小课堂", views: "9.5万", duration: "35:22", emoji: "🌐" },
  { id: 14, title: "VS Code 插件开发完整教程", author: "工具大师", views: "2.8万", duration: "22:10", emoji: "🔧" },
  { id: 15, title: "函数式编程思维：用 Haskell 写业务", author: "Lambda学派", views: "1.9万", duration: "19:44", emoji: "λ" },
  { id: 16, title: "网络安全攻防：XSS 漏洞深度解析", author: "白帽联盟", views: "15.3万", duration: "11:28", emoji: "🔒", badge: { text: "最新", color: "#23ADE5" } },
  { id: 17, title: "Redis 缓存策略全攻略", author: "高性能之路", views: "7.6万", duration: "13:50", emoji: "⚡" },
  { id: 18, title: "Kubernetes 入门：从 Pod 开始", author: "云原生布道师", views: "10.1万", duration: "28:33", emoji: "☸️" },
  { id: 19, title: "Git 高级技巧：rebase 还是 merge？", author: "版本控制控", views: "6.8万", duration: "07:42", emoji: "🔀" },
  { id: 20, title: "微服务架构中的服务发现与负载均衡", author: "分布式达人", views: "4.5万", duration: "17:19", emoji: "🔗" },
];

const CATEGORIES = ["推荐", "热门", "最新", "后端", "前端", "人工智能", "操作系统", "数据库", "运维", "安全"];

const COLORS = [
  "linear-gradient(135deg, #667eea, #764ba2)",
  "linear-gradient(135deg, #f093fb, #f5576c)",
  "linear-gradient(135deg, #4facfe, #00f2fe)",
  "linear-gradient(135deg, #43e97b, #38f9d7)",
  "linear-gradient(135deg, #fa709a, #fee140)",
  "linear-gradient(135deg, #a18cd1, #fbc2eb)",
  "linear-gradient(135deg, #fccb90, #d57eeb)",
  "linear-gradient(135deg, #e0c3fc, #8ec5fc)",
];

export default function HomePage() {
  const [user, setUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState("推荐");
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api.me().then((data) => setUser({...data.user, avatar: data.profile.avatar, nickname: data.profile.nickname})).catch(() => setUser(null));
  }, []);

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      navigate("/login");
    }
  };

  const filteredContent = searchQuery
    ? MOCK_CONTENT.filter((item) =>
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.author.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : MOCK_CONTENT;

  return (
    <div className="home-page">
      {/* Navigation */}
      <nav className="bili-nav">
        <div className="bili-nav-inner">
          <div className="bili-logo">
            <div className="bili-logo-icon">B</div>
            <span className="bili-logo-text">Backend</span>
          </div>

          <div className="bili-search">
            <input
              type="text"
              placeholder="搜索内容..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button className="bili-search-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
            </button>
          </div>

          <div className="bili-nav-right">
            {user ? (
              <>
                <div className="bili-user-info" onClick={() => navigate("/profile")} style={{ cursor: "pointer" }}>
                  <div className="bili-avatar">
                    {user.avatar ? (
                      <img src={user.avatar} alt="" />
                    ) : (
                      user.username.charAt(0).toUpperCase()
                    )}
                  </div>
                  <span className="bili-username">{user.nickname || user.username}</span>
                </div>
                <a className="bili-admin-link" href="/admin/" target="_blank" rel="noreferrer">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                  管理
                </a>
                <button className="bili-logout-btn" onClick={handleLogout}>
                  退出
                </button>
              </>
            ) : (
              <button className="bili-login-btn" onClick={() => navigate("/login")}>
                登录
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* Category Tabs */}
      <div className="bili-tabs-wrapper">
        <div className="bili-tabs">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              className={`bili-tab ${activeTab === cat ? "active" : ""}`}
              onClick={() => setActiveTab(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Content Grid */}
      <main className="bili-content">
        {!user ? (
          <div className="bili-loading">
            <div className="bili-loading-spinner" />
            加载中...
          </div>
        ) : (
          <div className="bili-grid">
            {filteredContent.map((item) => (
              <div key={item.id} className="bili-card">
                <div className="bili-card-thumb">
                  <div
                    className="bili-card-thumb-inner"
                    style={{ background: COLORS[item.id % COLORS.length] }}
                  >
                    {item.emoji}
                  </div>
                  <div className="bili-card-overlay">
                    <div className="bili-play-icon">
                      <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </div>
                  </div>
                  <span className="bili-card-duration">{item.duration}</span>
                  {item.badge && (
                    <span
                      className="bili-card-badge"
                      style={{ background: item.badge.color }}
                    >
                      {item.badge.text}
                    </span>
                  )}
                </div>
                <div className="bili-card-body">
                  <div className="bili-card-title">{item.title}</div>
                  <div className="bili-card-meta">
                    <div className="bili-card-author">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13, flexShrink: 0 }}>
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                      <span className="bili-card-author-name">{item.author}</span>
                    </div>
                    <div className="bili-card-stats">
                      <span className="bili-stat">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                        {item.views}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
