import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import Avatar from "../components/Avatar";
import ArticleToc, { htmlWithHeadingIds } from "../components/ArticleToc";
import PageChrome from "../components/PageChrome";
import { newsApi } from "../api/news";
import { type NewsDetail } from "../types/news";
import { useEmbedMode } from "../embed";
import "../styles/news.css";
import "../styles/form.css";

const fmtDate = (d: string | null) => {
  if (!d) return "—";
  const dt = new Date(d);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}.${p(dt.getMonth() + 1)}.${p(dt.getDate())}`;
};

export default function NewsDetailPage({
  embedded,
  newsId,
}: {
  embedded?: boolean;
  newsId?: number;
} = {}) {
  const params = useParams<{ id: string }>();
  const id = newsId != null ? String(newsId) : params.id;
  const navigate = useNavigate();
  const urlEmbed = useEmbedMode();
  const embed = Boolean(embedded || urlEmbed);
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

  if (loading) return <PageChrome embedded={embed}><div className="container"><p className="news-empty">加载中…</p></div></PageChrome>;
  if (error && !news) return <PageChrome embedded={embed}><div className="container"><p className="news-empty">{error}</p></div></PageChrome>;
  if (!news) return <PageChrome embedded={embed}><div className="container"><p className="news-empty">新闻不存在或已下线。</p></div></PageChrome>;

  const related = news.related || [];
  const prepared = htmlWithHeadingIds(news.content || "");

  return (
    <PageChrome embedded={embed}>
      <div className="container">
        <div className="detail-layout">
          <article className="article">
            {!embed && (
            <nav className="breadcrumb" style={{ marginTop: "var(--s-8)" }}>
              <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
              <span className="sep">/</span>
              <a href="#" onClick={(e) => { e.preventDefault(); navigate("/news"); }}>新闻</a>
              <span className="sep">/</span>
              <span>{news.title}</span>
            </nav>
            )}

            {!embed && news.review_status === "pending" && (
              <div className="form-notice" style={{ margin: "12px 0" }}>此稿待审，仅你与审核员可见，尚未对公众公开。</div>
            )}
            {!embed && news.review_status === "rejected" && (
              <div className="alert alert-warning" style={{ margin: "12px 0" }}>此稿已驳回，不对公众展示。</div>
            )}
            {!embed && news.review_status === "removed" && (
              <div className="alert alert-warning" style={{ margin: "12px 0" }}>此稿已下架，不对公众展示。</div>
            )}
            <h1>{news.title}</h1>

            <div className="article-meta">
              <span className="author">
                <Link to={`/u/${news.author.id}`}><Avatar user={news.author} size="sm" /></Link>
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
              <div className="prose" dangerouslySetInnerHTML={{ __html: prepared.html }} />
            ) : (
              <div className="prose"><p className="lead">（暂无正文）</p></div>
            )}

            {news.tags.length > 0 && (
              <div className="article-tags">
                {news.tags.map((t) => <span key={t.id} className="chip">{t.name}</span>)}
              </div>
            )}

            {!embed && (
            <div className="article-actions">
              <button className="btn btn-secondary" onClick={() => navigate("/news")}>
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M11 6l-6 6 6 6" /></svg> 返回列表
              </button>
              <button className="btn btn-ghost" onClick={copyLink}>
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a4 4 0 0 0 5.7.4l3-3a4 4 0 0 0-5.7-5.7l-1.4 1.4" /><path d="M14 11a4 4 0 0 0-5.7-.4l-3 3a4 4 0 0 0 5.7 5.7l1.4-1.4" /></svg> {copied ? "已复制" : "复制链接"}
              </button>
            </div>
            )}

            <div className="author-card">
              <Link to={`/u/${news.author.id}`}><Avatar user={news.author} size="md" /></Link>
              <div>
                <div className="ac-name">{news.author.nickname || news.author.username}</div>
                <div className="ac-desc">@{news.author.username} · 本内容由信息组发布。</div>
              </div>
            </div>
          </article>

          <aside className="detail-side">
            <ArticleToc html={news.content || ""} />
            <div className="side-card">
              <h4><span className="bar" /> 文章信息</h4>
              <div className="meta-row"><span className="k">发布</span><span className="v tnum">{fmtDate(news.published_at || news.created_at)}</span></div>
              <div className="meta-row"><span className="k">来源</span><span className="v">传媒社</span></div>
              <div className="meta-row"><span className="k">阅读</span><span className="v">{news.views}</span></div>
            </div>
            {!embed && related.length > 0 && (
              <div className="side-card">
                <h4><span className="bar" /> 相关阅读</h4>
                {related.map((r) => (
                  <a key={r.id} className="rel-item" href="#"
                     onClick={(e) => { e.preventDefault(); navigate(`/news/${r.id}`); }}>
                    <h5>{r.title}</h5>
                    <span className="rdate">{fmtDate(r.published_at || r.created_at)}</span>
                  </a>
                ))}
              </div>
            )}
          </aside>
        </div>

        {!embed && related.length > 0 && (
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
                    <span className="date tnum">{fmtDate(r.published_at || r.created_at)}</span>
                    <h3 style={{ marginTop: "10px" }}>{r.title}</h3>
                  </div>
                </a>
              ))}
            </div>
          </section>
        )}
      </div>
    </PageChrome>
  );
}
