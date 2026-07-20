import { CATEGORY_BADGE_CLASS, CATEGORY_LABELS } from "../../types/news";
import {
  ACTIVITY_META,
  ACTIVITY_PHASE_LABEL,
  FEED_TASK_PRIORITY_BARS,
  FEED_TASK_STATUS_LABEL,
  type ActivityFeedItem,
  type NewsFeedItem,
  type TaskFeedItem,
  type FeedTaskPriority,
} from "../../types/feed";

function PriorityBars({ priority }: { priority: FeedTaskPriority }) {
  const on = FEED_TASK_PRIORITY_BARS[priority];
  return (
    <span className="feed-prio">
      {[0, 1, 2].map((i) => (
        <i key={i} className={i < on ? "on" : ""} />
      ))}
    </span>
  );
}

function Cover({ url, emoji = "📰" }: { url: string | null; emoji?: string }) {
  return (
    <div
      className="feed-cover"
      style={url ? { backgroundImage: `url(${url})` } : undefined}
    >
      {!url && <span className="feed-cover-emoji">{emoji}</span>}
    </div>
  );
}

export function FeaturedNewsCard({ item, onClick }: { item: NewsFeedItem; onClick: () => void }) {
  return (
    <button type="button" className="feed-featured" onClick={onClick}>
      <Cover url={item.cover_image_url} />
      <div className="feed-featured-body">
        <span className={`badge ${CATEGORY_BADGE_CLASS[item.category]}`}>
          {CATEGORY_LABELS[item.category]}
        </span>
        <h3>{item.title}</h3>
        {item.summary && <p>{item.summary}</p>}
        <div className="feed-meta">
          <span>👁 {item.views}</span>
        </div>
      </div>
    </button>
  );
}

export function NewsCard({ item, onClick }: { item: NewsFeedItem; onClick: () => void }) {
  return (
    <button type="button" className="feed-cell feed-cell--news" onClick={onClick}>
      <Cover url={item.cover_image_url} />
      <div className="feed-cell-body">
        <span className={`badge ${CATEGORY_BADGE_CLASS[item.category]}`}>
          {CATEGORY_LABELS[item.category]}
        </span>
        <h4>{item.title}</h4>
        <div className="feed-meta">
          <span>👁 {item.views}</span>
        </div>
      </div>
    </button>
  );
}

export function ActivityCard({ item, onClick }: { item: ActivityFeedItem; onClick: () => void }) {
  const meta = ACTIVITY_META[item.activity_type] ?? { label: "活动", emoji: "🎉" };
  return (
    <button type="button" className="feed-cell feed-cell--activity" onClick={onClick}>
      <div className="feed-act-head">
        <span className="badge badge-brand">{meta.label}</span>
        <span className="feed-emoji">{meta.emoji}</span>
      </div>
      <h4>{item.title}</h4>
      <div className="feed-act-foot">
        {item.planned_date && <span>📅 {item.planned_date}</span>}
        {item.location && <span>📍 {item.location}</span>}
        {item.expected_participants != null && <span>👥 {item.expected_participants}</span>}
      </div>
      {item.phase && (
        <span className={`feed-phase feed-phase--${item.phase}`}>
          {ACTIVITY_PHASE_LABEL[item.phase]}
        </span>
      )}
    </button>
  );
}

export function TaskCard({ item, onClick }: { item: TaskFeedItem; onClick: () => void }) {
  return (
    <button type="button" className="feed-cell feed-cell--task" onClick={onClick}>
      <div className="feed-task-head">
        <span className={`feed-status feed-status--${item.status}`}>
          {FEED_TASK_STATUS_LABEL[item.status]}
        </span>
        <PriorityBars priority={item.priority} />
      </div>
      <h4>{item.title}</h4>
      <div className="feed-meta">
        {item.assignee ? `@${item.assignee.nickname || item.assignee.username}` : "未指派"}
      </div>
    </button>
  );
}
