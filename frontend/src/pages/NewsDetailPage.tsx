import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../components/AppShell";
import Avatar from "../components/Avatar";
import { newsApi } from "../api/news";
import { type NewsDetail, CATEGORY_LABELS, CATEGORY_BADGE_CLASS } from "../types/news";
import "../styles/news.css";

const fmtDate = (d: string | null) => {
  if (!d) return "—";
  const dt = new Date(d);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}.${p(dt.getMonth() + 1)}.${p(dt.getDate())}`;
};

export default function NewsDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [news, setNews] = useState<NewsDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    newsApi.get(Number(id))
      .then(setNews)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const copyLink = async () => {
    try { await navigator.clipboard.writeText(window.location.href); } catch { /* ignore */ }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  if (loading) return <AppShell><div className="container"><p className="news-empty">加载中…</p></div></AppShell>;
  if (error && !news) return <AppShell><div className="container"><p className="news-empty">{error}</p></div></AppShell>;
  if (!news) return <AppShell><div className="container"><p className="news-empty">新闻不存在或已下线。</p></div></AppShell>;

  const related = news.related || [];

  return (
    <AppShell>
      <div className="container">
        <div className="detail-layout">
          <article className="article">
            <nav className="breadcrumb" style={{ marginTop: "var(--s-8)" }}>
              <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
              <span className="sep">/</span>
              <a href="#" onClick={(e) => { e.preventDefault(); navigate("/news"); }}>新闻</a>
              <span className="sep">/</span>
              <span>{CATEGORY_LABELS[news.category]}</span>
            </nav>

            <span className="badge badge-brand article-cat"><span className="badge-dot" />{CATEGORY_LABELS[news.category]}</span>
            <h1>{news.title}</h1>

            <div className="article-meta">
              <span className="author">
                <Avatar user={news.author} size="sm" />
                {news.author.nickname || news.author.username}
              </span>
              <span className="sep">·</span>
              <span className="date tnum">{fmtDate(news.published_at || news.created_at)}</span>
              <span className="sep">·</span>
              <span>阅读 {news.views}</span>
              <span className="sep">·</span>
              <span>来源：传媒社</span>
            </div>

            <div className={"article-hero" + (news.cover_image_url ? "" : " ph-img")}>
              {news.cover_image_url ? (
                <img src={news.cover_image_url} alt={news.title} />
              ) : (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h3l2-2h6l2 2h3v11H4z" /><circle cx="12" cy="13" r="3.2" /></svg>
                  <span className="ph-label">头图 · 待补充</span>
                </>
              )}
            </div>

            {news.content ? (
              <div className="prose" dangerouslySetInnerHTML={{ __html: news.content }} />
            ) : (
              <div className="prose"><p className="lead">（暂无正文）</p></div>
            )}

            {news.tags.length > 0 && (
              <div className="article-tags">
                {news.tags.map((t) => <span key={t.id} className="chip">{t.name}</span>)}
              </div>
            )}

            <div className="article-actions">
              <button className="btn btn-secondary" onClick={() => navigate("/news")}>
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M11 6l-6 6 6 6" /></svg> 返回列表
              </button>
              <button className="btn btn-ghost" onClick={copyLink}>
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a4 4 0 0 0 5.7.4l3-3a4 4 0 0 0-5.7-5.7l-1.4 1.4" /><path d="M14 11a4 4 0 0 0-5.7-.4l-3 3a4 4 0 0 0 5.7 5.7l1.4-1.4" /></svg> {copied ? "已复制" : "复制链接"}
              </button>
            </div>

            <div className="author-card">
              <Avatar user={news.author} size="md" />
              <div>
                <div className="ac-name">{news.author.nickname || news.author.username}</div>
                <div className="ac-desc">@{news.author.username} · 本内容由信息组发布。</div>
              </div>
            </div>
          </article>

          <aside className="detail-side">
            <div className="side-card">
              <h4><span className="bar" /> 文章信息</h4>
              <div className="meta-row"><span className="k">分类</span><span className="v">{CATEGORY_LABELS[news.category]}</span></div>
              <div className="meta-row"><span className="k">发布</span><span className="v tnum">{fmtDate(news.published_at || news.created_at)}</span></div>
              <div className="meta-row"><span className="k">来源</span><span className="v">传媒社</span></div>
              <div className="meta-row"><span className="k">阅读</span><span className="v">{news.views}</span></div>
            </div>
            {related.length > 0 && (
              <div className="side-card">
                <h4><span className="bar" /> 相关阅读</h4>
                {related.map((r) => (
                  <a key={r.id} className="rel-item" href="#"
                     onClick={(e) => { e.preventDefault(); navigate(`/news/${r.id}`); }}>
                    <span className="rcat">{CATEGORY_LABELS[r.category]}</span>
                    <h5>{r.title}</h5>
                    <span className="rdate">{fmtDate(r.published_at || r.created_at)}</span>
                  </a>
                ))}
              </div>
            )}
          </aside>
        </div>

        {related.length > 0 && (
          <section style={{ paddingBottom: "var(--s-16)" }}>
            <div className="section-head">
              <div>
                <div className="eyebrow">MORE · 继续阅读</div>
                <h2 className="section-title"><span className="bar" /> 相关推荐</h2>
              </div>
            </div>
            <div className="related-grid">
              {related.map((r) => (
                <a key={r.id} className="card card-hover" href="#"
                   onClick={(e) => { e.preventDefault(); navigate(`/news/${r.id}`); }}>
                  <div className={"card-media" + (r.cover_image_url ? "" : " ph-img")}>
                    {r.cover_image_url ? (
                      <img src={r.cover_image_url} alt={r.title} />
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8" /><path d="M4 12h16" /></svg>
                    )}
                  </div>
                  <div className="card-body">
                    <span className={"badge " + CATEGORY_BADGE_CLASS[r.category]}>{CATEGORY_LABELS[r.category]}</span>
                    <h3 style={{ marginTop: "10px" }}>{r.title}</h3>
                  </div>
                </a>
              ))}
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}
