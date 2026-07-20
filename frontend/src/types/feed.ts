import type { NewsCategory } from "./news";

export type FeedType = "news" | "activity" | "task";

export type ActivityType = "competition" | "training" | "project" | "sharing" | "event";
export type ActivityPhase = "upcoming" | "ongoing" | "ended";
export type FeedTaskStatus = "pending" | "in_progress" | "reviewing" | "review";
export type FeedTaskPriority = "low" | "medium" | "high" | "urgent";

export interface FeedAssignee {
  id: number;
  username: string;
  nickname: string;
  avatar: string | null;
}

interface FeedItemBase {
  type: FeedType;
  id: number;
  title: string;
  timestamp: string; // ISO8601，排序依据
}

export interface NewsFeedItem extends FeedItemBase {
  type: "news";
  category: NewsCategory;
  summary: string;
  cover_image_url: string | null;
  views: number;
}

export interface ActivityFeedItem extends FeedItemBase {
  type: "activity";
  activity_type: ActivityType;
  phase: ActivityPhase | null;
  planned_date: string | null;
  location: string;
  expected_participants: number | null;
}

export interface TaskFeedItem extends FeedItemBase {
  type: "task";
  status: FeedTaskStatus;
  priority: FeedTaskPriority;
  assignee: FeedAssignee | null;
}

export type FeedItem = NewsFeedItem | ActivityFeedItem | TaskFeedItem;

export interface FeedResponse {
  featured: NewsFeedItem | null;
  items: FeedItem[];
}

// —— 展示映射 ——
export const ACTIVITY_META: Record<ActivityType, { label: string; emoji: string }> = {
  competition: { label: "比赛", emoji: "📷" },
  training: { label: "培训", emoji: "🎬" },
  project: { label: "项目", emoji: "🎥" },
  sharing: { label: "分享", emoji: "💡" },
  event: { label: "活动", emoji: "🎉" },
};

export const ACTIVITY_PHASE_LABEL: Record<ActivityPhase, string> = {
  upcoming: "即将开始",
  ongoing: "进行中",
  ended: "已结束",
};

export const FEED_TASK_STATUS_LABEL: Record<FeedTaskStatus, string> = {
  pending: "待处理",
  in_progress: "进行中",
  reviewing: "待验收",
  review: "审核中",
};

export const FEED_TASK_PRIORITY_LABEL: Record<FeedTaskPriority, string> = {
  low: "低",
  medium: "中",
  high: "高",
  urgent: "紧急",
};

// 优先级条形格数（1~3）
export const FEED_TASK_PRIORITY_BARS: Record<FeedTaskPriority, number> = {
  low: 1,
  medium: 2,
  high: 3,
  urgent: 3,
};
