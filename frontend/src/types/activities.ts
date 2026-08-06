import type { TaskUser, Attachment } from "./tasks";

// 活动（ADR 0007）：众议（投票）/ 征集（收作品）。独立于申报（反馈）。

export type ActivityType = "deliberation" | "collection";
export type ActivityStatus =
  | "open" // 众议：投票中
  | "closed" // 众议：已截止结算
  | "collecting" // 征集：收件中
  | "reviewing" // 征集：复审中
  | "archived"; // 征集：已归档
export type ReviewStatus = "pending" | "accepted" | "rejected";

export interface ActivityListItem {
  id: number;
  type: ActivityType;
  status: ActivityStatus;
  title: string;
  creator: TaskUser | null;
  end_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VoteOption {
  id: number;
  text: string;
  order: number;
  vote_count: number;
}

export interface Ballot {
  id: number;
  voter: TaskUser;
  option_ids: number[];
  created_at: string;
}

export interface Submission {
  id: number;
  submitter: TaskUser;
  files: Attachment[];
  review_status: ReviewStatus;
  review_comment: string;
  reviewed_at: string | null;
  created_at: string;
}

export interface ActivityDetail {
  id: number;
  type: ActivityType;
  status: ActivityStatus;
  title: string;
  body: string;
  creator: TaskUser | null;
  end_at: string | null;
  // 众议
  max_choices_per_voter: number;
  is_secret_ballot: boolean;
  options: VoteOption[];
  ballots: Ballot[] | null; // 秘密投票下非超管为 null
  my_selections: number[] | null;
  total_ballots: number | null;
  // 征集
  allowed_extensions: string;
  max_file_size: number | null;
  max_files_per_submission: number;
  max_submissions: number | null;
  my_submission: Submission | null;
  submissions: Submission[] | null; // 复审者见全部；其余仅录用（公开展示）
  created_at: string;
  updated_at: string;
}

// ---- 创建表单 ----
export interface DeliberationFormData {
  type: "deliberation";
  title: string;
  body: string;
  max_choices_per_voter: number;
  is_secret_ballot: boolean;
  end_at?: string;
  option_texts: string[];
}

export interface CollectionFormData {
  type: "collection";
  title: string;
  body: string;
  allowed_extensions: string;
  max_file_size: number | null;
  max_files_per_submission: number;
  max_submissions: number | null;
  end_at?: string;
}

export type ActivityFormData = DeliberationFormData | CollectionFormData;

// ---- 标签 ----
export const ACTIVITY_TYPE_LABELS: Record<ActivityType, string> = {
  deliberation: "众议",
  collection: "征集",
};

export const ACTIVITY_STATUS_LABELS: Record<ActivityStatus, string> = {
  open: "投票中",
  closed: "已结束",
  collecting: "收件中",
  reviewing: "复审中",
  archived: "已归档",
};

export const ACTIVITY_STATUS_BADGE_CLASS: Record<ActivityStatus, string> = {
  open: "badge-brand",
  closed: "badge-neutral",
  collecting: "badge-brand",
  reviewing: "badge-warning",
  archived: "badge-neutral",
};

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "待复审",
  accepted: "录用",
  rejected: "退稿",
};

export const REVIEW_STATUS_BADGE_CLASS: Record<ReviewStatus, string> = {
  pending: "badge-warning",
  accepted: "badge-success",
  rejected: "badge-neutral",
};
