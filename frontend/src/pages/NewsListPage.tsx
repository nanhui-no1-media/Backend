import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import { api } from "../api/client";
import { newsApi } from "../api/news";
import {
  type NewsCategory,
  type NewsListItem,
  type NewsTag,
  CATEGORY_LABELS, CATEGORY_BADGE_CLASS, NEWS_PAGE_SIZE,
} from "../types/news";
import "../styles/news.css";

const fmtDate = (d: string | null) => {
  if (!d) return "";
  const dt = new Date(d);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}.${p(dt.getMonth() + 1)}.${p(dt.getDate())}`;
};

interface Me { can_manage_news?: boolean }

export default function NewsListPage() {
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [featured, setFeatured] = useState<NewsListItem | null>(null);
  const [items, setItems] = useState<NewsListItem[]>([]);
  const [count, setCount] = useState(0);
  const [hot, setHot] = useState<NewsListItem[]>([]);
  const [tagCloud, setTagCloud] = useState<NewsTag[]>([]);
  const [category, setCategory] = useState<NewsCategory | "">("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  // 公开页：匿名也可读，故 me() 失败静默（不弹登录）
  useEffect(() => {
    api.me().then((d: any) => setMe({ can_manage_news: d.user?.permissions?.can_manage_news })).catch(() => {});
  }, []);

  useEffect(() => {
    newsApi.featured().then(setFeatured).catch(() => {});
    newsApi.hot().then(setHot).catch(() => {});
    newsApi.tags().then(setTagCloud).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page) };
    if (category) params.category = category;
    if (search) params.search = search;
    newsApi.list(params)
      .then((data) => { setItems(data.results || []); setCount(data.count); })
      .catch(() => { setItems([]); setCount(0); })
      .finally(() => setLoading(false));
  }, [category, search, page]);

  const totalPages = Math.max(1, Math.ceil(count / NEWS_PAGE_SIZE));
  const showFeatured = !category && !search && page === 1;
  // 头条同时在列表中出现会重复，hero 展示时从列表中剔除
  const visibleItems = showFeatured && featured ? items.filter((n) => n.id !== featured.id) : items;

  const pickCategory = (c: NewsCategory | "") => { setCategory(c); setPage(1); };
  const onSearch = (v: string) => { setSearch(v); setPage(1); };

  // 分页按钮：1 … (page-1,page,page+1) … totalPages
  const pagerEntries = (): (number | "ellipsis")[] => {
    const nums = new Set<number>([1, totalPages, page, page - 1, page + 1]);
    const sorted = [...nums].filter((n) => n >= 1 && n <= totalPages).sort((a, b) => a - b);
    const out: (number | "ellipsis")[] = [];
    let prev = 0;
    for (const n of sorted) {
      if (prev && n - prev > 1) out.push("ellipsis");
      out.push(n);
      prev = n;
    }
    return out;
  };

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>新闻</span>
          </nav>
          <div className="page-head-row">
            <div>
              <h1>新闻</h1>
              <p className="section-sub">社团公告、活动回顾、社员作品与通知。</p>
            </div>
            {me?.can_manage_news && (
              <button className="btn btn-primary" onClick={() => navigate("/news/new")}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
                写新闻
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="container">
        <div className="filter-bar" role="tablist" aria-label="新闻分类">
          <button className="chip" aria-pressed={category === ""} onClick={() => pickCategory("")}>全部</button>
          {(Object.keys(CATEGORY_LABELS) as NewsCategory[]).map((c) => (
            <button key={c} className="chip" aria-pressed={category === c} onClick={() => pickCategory(c)}>
              {CATEGORY_LABELS[c]}
            </button>
          ))}
        </div>

        <div className="news-layout">
          <div>
            {/* 头条：仅在未筛选首页展示 */}
            {showFeatured && featured && (
              <a className="feature" href="#"
                 onClick={(e) => { e.preventDefault(); navigate(`/news/${featured.id}`); }}>
                <div className={"feature-media" + (featured.cover_image_url ? "" : " ph-img")}>
                  {featured.cover_image_url ? (
                    <img src={featured.cover_image_url} alt={featured.title} />
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h3l2-2h6l2 2h3v11H4z" /><circle cx="12" cy="13" r="3.2" /></svg>
                      <span className="ph-label">头条配图</span>
                    </>
                  )}
                </div>
                <div className="feature-body">
                  <span className="badge badge-brand feature-tag"><span className="badge-dot" />{CATEGORY_LABELS[featured.category]} · 头条</span>
                  <h2>{featured.title}</h2>
                  <p>{featured.summary}</p>
                  <div className="feature-meta">
                    <span className="date tnum">{fmtDate(featured.published_at || featured.created_at)}</span>
                    <span>· {featured.author.nickname || featured.author.username}</span>
                    <span>· 阅读 {featured.views}</span>
                  </div>
                </div>
              </a>
            )}

            {/* 列表 */}
            {loading ? (
              <p className="news-empty">加载中…</p>
            ) : visibleItems.length === 0 ? (
              <p className="news-empty">{category || search ? "该筛选下暂无内容。" : "暂无新闻。"}</p>
            ) : (
              visibleItems.map((n) => (
                <a key={n.id} className="news-item" href="#"
                   onClick={(e) => { e.preventDefault(); navigate(`/news/${n.id}`); }}>
                  <div className={"thumb" + (n.cover_image_url ? "" : " ph-img")}>
                    {n.cover_image_url ? (
                      <img src={n.cover_image_url} alt={n.title} />
                    ) : (
                      <>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h16v12H4z" /><path d="M4 6h16M9 10h6" /></svg>
                        <span className="ph-label">配图</span>
                      </>
                    )}
                  </div>
                  <div>
                    <div className="meta">
                      <span className={"badge " + CATEGORY_BADGE_CLASS[n.category]}>{CATEGORY_LABELS[n.category]}</span>
                      <span className="date tnum">{fmtDate(n.published_at || n.created_at)}</span>
                    </div>
                    <h3>{n.title}</h3>
                    <p>{n.summary}</p>
                    <span className="read">阅读 {n.views}</span>
                  </div>
                </a>
              ))
            )}

            {/* 分页 */}
            {!loading && totalPages > 1 && (
              <nav className="pager" aria-label="分页" style={{ marginTop: "var(--s-10)" }}>
                <button aria-label="上一页" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
                </button>
                {pagerEntries().map((b, i) =>
                  b === "ellipsis" ? (
                    <span key={"e" + i} className="ellipsis">…</span>
                  ) : (
                    <button key={b} aria-current={b === page ? "page" : undefined} onClick={() => setPage(b)}>{b}</button>
                  )
                )}
                <button aria-label="下一页" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
                </button>
              </nav>
            )}
          </div>

          {/* 侧栏 */}
          <aside className="side">
            <div className="side-card">
              <div className="input-affix">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
                <input className="input" type="search" placeholder="搜索新闻…" aria-label="搜索新闻"
                       value={search} onChange={(e) => onSearch(e.target.value)} />
              </div>
            </div>
            <div className="side-card">
              <h4><span className="bar" /> 热门阅读</h4>
              <ul className="hot-list">
                {hot.length === 0 ? (
                  <li><span className="rank">·</span><div><span style={{ color: "var(--faint)", fontSize: 13 }}>暂无数据</span></div></li>
                ) : hot.map((n, i) => (
                  <li key={n.id}>
                    <span className="rank">{String(i + 1).padStart(2, "0")}</span>
                    <div>
                      <a href="#" onClick={(e) => { e.preventDefault(); navigate(`/news/${n.id}`); }}>{n.title}</a>
                      <div className="hv">阅读 {n.views}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div className="side-card">
              <h4><span className="bar" /> 标签</h4>
              <div className="tag-cloud">
                {tagCloud.length === 0 ? (
                  <span className="chip">暂无标签</span>
                ) : tagCloud.map((t) => (
                  <span key={t.id} className="chip">{t.name}{typeof t.news_count === "number" ? ` · ${t.news_count}` : ""}</span>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
