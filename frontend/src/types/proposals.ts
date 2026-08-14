import type { TaskUser, Attachment } from "./tasks";

// 申报 = 意见反馈（活动已分离至 activities app，ADR 0007）。此文件仅承载反馈。

export type ProposalStatus = "pending_approval" | "approved" | "rejected" | "withdrawn";
export type FeedbackCategory = "suggestion" | "complaint" | "report" | "other";

export interface ProposalAttachment extends Attachment {}

export interface ProposalListItem {
  id: number;
  status: ProposalStatus;
  title: string;
  creator: TaskUser | null; // 匿名反馈为 null
  contact: string;
  feedback_category: FeedbackCategory | "";
  reject_reason: string;
  attachment_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProposalDetail {
  id: number;
  status: ProposalStatus;
  title: string;
  description: string;
  feedback_category: FeedbackCategory | "";
  contact: string;
  creator: TaskUser | null;
  reviewed_by: TaskUser | null;
  reviewed_at: string | null;
  approved_at: string | null;
  attachments: ProposalAttachment[];
  reject_reason: string;
  created_at: string;
  updated_at: string;
}

export interface FeedbackFormData {
  title: string;
  description: string;
  feedback_category: FeedbackCategory | "";
  contact?: string;
  // 署名提交（登录用户显式选择）：记录 creator、对社长可见、方可附媒体。
  disclose_identity?: boolean;
}

export const PROPOSAL_STATUS_LABELS: Record<ProposalStatus, string> = {
  pending_approval: "待社长审批",
  approved: "已通过",
  rejected: "已拒绝",
  withdrawn: "已撤回",
};

export const PROPOSAL_STATUS_BADGE_CLASS: Record<ProposalStatus, string> = {
  pending_approval: "badge-warning",
  approved: "badge-success",
  rejected: "badge-neutral",
  withdrawn: "badge-neutral",
};

export const FEEDBACK_CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  suggestion: "建议",
  complaint: "投诉",
  report: "举报",
  other: "其他",
};
