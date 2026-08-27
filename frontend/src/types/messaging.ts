import type { TaskUser } from "./tasks";

export type ThreadStatus = "open" | "muted" | "closed";

export type CommentHost =
  | { news: number }
  | { activity: number }
  | { task: number };

export interface CommentThread {
  id: number;
  status: ThreadStatus;
  news: number | null;
  activity: number | null;
  task: number | null;
  can_manage: boolean;
}

export interface Comment {
  id: number;
  thread: number;
  author: TaskUser;
  parent: number | null;
  content: string;
  retracted_at: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  replies: Comment[];
}

export interface Conversation {
  id: number;
  title: string;
  participants: TaskUser[];
  last_message: DirectMessage | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
}

export interface DirectMessage {
  id: number;
  conversation: number;
  sender: TaskUser;
  content: string;
  mentions: TaskUser[];
  is_read: boolean;
  retracted_at: string | null;
  created_at: string;
  updated_at: string;
}

export type NotificationCategory = "comment" | "review" | "discipline";

export interface Notification {
  id: number;
  category: NotificationCategory;
  event: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface Banner {
  id: number;
  body: string;
  link: string;
  starts_at: string;
  ends_at: string;
  priority: number;
}

export interface UserMute {
  id: number;
  user: number;
  muted_by: number;
  reason: string;
  starts_at: string;
  ends_at: string | null;
  lifted_at: string | null;
}

export interface MuteStatus {
  muted: boolean;
  mute: UserMute | null;
}

export const THREAD_STATUS_LABELS: Record<ThreadStatus, string> = {
  open: "开放",
  muted: "评论区禁言",
  closed: "彻底关闭",
};

export const NOTIFICATION_CATEGORY_LABELS: Record<NotificationCategory, string> = {
  comment: "评论",
  review: "审核",
  discipline: "纪律",
};

export const NOTIFICATION_EVENT_LABELS: Record<string, string> = {
  comment_replied: "有人回复了你的评论",
  comment_mentioned: "有人在评论中提到了你",
  comment_posted: "有新的评论",
  muted: "你已被全站禁言",
  mute_lifted: "全站禁言已解除",
  mute_expired: "全站禁言已到期",
  approved: "内容已通过审核",
  rejected: "内容未通过审核",
  removed: "内容已下架",
};

export const RETRACT_WINDOW_MS = 3 * 60 * 1000;

export function withinRetractWindow(createdAt: string, now = Date.now()): boolean {
  const t = new Date(createdAt).getTime();
  return Number.isFinite(t) && now - t < RETRACT_WINDOW_MS;
}

export function hostQuery(host: CommentHost): Record<string, string> {
  if ("news" in host) return { news: String(host.news) };
  if ("activity" in host) return { activity: String(host.activity) };
  return { task: String(host.task) };
}

export function notificationHref(n: Notification): string | null {
  const p = n.payload || {};
  const url = p.url;
  if (typeof url === "string" && url) {
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
    return url.startsWith("/") ? url : `/${url}`;
  }
  if (typeof p.news_id === "number") return `/news/${p.news_id}`;
  if (typeof p.activity_id === "number") return `/activity/${p.activity_id}`;
  if (typeof p.task_id === "number") return `/tasks/${p.task_id}`;
  return null;
}

export function notificationTitle(n: Notification): string {
  return NOTIFICATION_EVENT_LABELS[n.event]
    || NOTIFICATION_CATEGORY_LABELS[n.category]
    || "通知";
}
