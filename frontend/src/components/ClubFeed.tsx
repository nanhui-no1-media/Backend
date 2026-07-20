import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { newsApi } from "../api/news";
import { useLoginModal } from "./LoginModalProvider";
import { ActivityCard, FeaturedNewsCard, NewsCard, TaskCard } from "./feed/FeedCards";
import type { FeedItem, FeedResponse } from "../types/feed";

interface Props {
  // HomePage 的 user 状态：这里只需 id（登录态判定 + 重拉依赖）与真值（点击活动时游客/成员分流）
  user: { id: number } | null;
}

export default function ClubFeed({ user }: Props) {
  const [data, setData] = useState<FeedResponse | null>(null);
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();

  // 用户身份变化（登录/登出）时重拉，让任务格随之出现/消失
  useEffect(() => {
    newsApi.feed().then(setData).catch(() => setData(null));
  }, [user?.id]);

  const goNews = (id: number) => navigate(`/news/${id}`);
  const goTask = (id: number) => navigate(`/tasks/${id}`);
  const goActivity = (id: number) => {
    if (user) navigate(`/activity/${id}`);
    else openLogin(`/activity/${id}`); // 游客点活动 → 弹登录（引流）
  };

  const open = (item: FeedItem) => () => {
    if (item.type === "news") goNews(item.id);
    else if (item.type === "task") goTask(item.id);
    else goActivity(item.id);
  };

  const featured = data?.featured ?? null;
  const items = data?.items ?? [];
  const sizeFor = (i: number): "large" | "medium" | "small" =>
    i === 0 ? "large" : i === 1 ? "medium" : "small";

  return (
    <section>
      <div className="section-head">
        <div>
          <div className="eyebrow">CLUB · ACTIVITY</div>
          <h2 className="section-title">
            <span className="bar" /> 社团动态
          </h2>
        </div>
        <a
          className="section-link"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("/news");
          }}
        >
          全部动态
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </a>
      </div>

      {!data ? (
        <div className="feed-empty">加载中…</div>
      ) : !featured && items.length === 0 ? (
        <div className="feed-empty">暂无动态</div>
      ) : (
        <>
          {featured && <FeaturedNewsCard item={featured} onClick={() => goNews(featured.id)} />}
          {items.length > 0 && (
            <div className="feed-bento">
              {items.map((item, i) => (
                <div key={`${item.type}-${item.id}`} className={`feed-cell-wrap feed-cell-wrap--${sizeFor(i)}`}>
                  {item.type === "news" ? (
                    <NewsCard item={item} onClick={open(item)} />
                  ) : item.type === "activity" ? (
                    <ActivityCard item={item} onClick={open(item)} />
                  ) : (
                    <TaskCard item={item} onClick={open(item)} />
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
