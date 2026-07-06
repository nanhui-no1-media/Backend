import { TaskUser, Attachment } from "./tasks";

export type ProposalType = "activity" | "feedback";
export type ProposalStatus =
  | "voting"
  | "pending_approval"
  | "returned"
  | "approved"
  | "rejected"
  | "withdrawn";
export type VoteChoice = "approve" | "oppose" | "abstain";
export type ActivityType = "competition" | "training" | "project" | "sharing" | "event";
export type FeedbackCategory = "suggestion" | "complaint" | "report" | "other";

export interface VoteSummary {
  approve: number;
  oppose: number;
  abstain: number;
  total: number;
}

export interface Vote {
  id: number;
  voter: TaskUser;
  vote_choice: VoteChoice;
  created_at: string;
}

export interface ProposalAttachment extends Attachment {}

export interface ProposalListItem {
  id: number;
  proposal_type: ProposalType;
  status: ProposalStatus;
  title: string;
  creator: TaskUser | null; // 反馈/举报为 null（匿名）
  contact: string;
  activity_type: ActivityType | "";
  feedback_category: FeedbackCategory | "";
  voting_end_at: string | null;
  reject_reason: string;
  attachment_count: number;
  vote_summary: VoteSummary | null;
  created_at: string;
  updated_at: string;
}

export interface ProposalDetail {
  id: number;
  proposal_type: ProposalType;
  status: ProposalStatus;
  title: string;
  description: string;
  activity_type: ActivityType | "";
  planned_date: string | null;
  location: string;
  expected_participants: number | null;
  budget: string | null;
  feedback_category: FeedbackCategory | "";
  contact: string;
  creator: TaskUser | null;
  reviewed_by: TaskUser | null;
  reviewed_at: string | null;
  approved_at: string | null;
  votes: Vote[];
  my_vote: VoteChoice | null;
  attachments: ProposalAttachment[];
  voting_end_at: string | null;
  reject_reason: string;
  created_at: string;
  updated_at: string;
}

export interface ActivityFormData {
  proposal_type: "activity";
  title: string;
  description: string;
  activity_type: ActivityType | "";
  planned_date?: string | null;
  location?: string;
  expected_participants?: number | null;
  budget?: number | null;
}

export interface FeedbackFormData {
  proposal_type: "feedback";
  title: string;
  description: string;
  feedback_category: FeedbackCategory | "";
  contact?: string;
}

export const PROPOSAL_TYPE_LABELS: Record<ProposalType, string> = {
  activity: "活动申报",
  feedback: "意见反馈",
};

export const PROPOSAL_STATUS_LABELS: Record<ProposalStatus, string> = {
  voting: "投票中",
  pending_approval: "待社长审批",
  returned: "已打回",
  approved: "已通过",
  rejected: "已拒绝",
  withdrawn: "已撤回",
};

export const PROPOSAL_STATUS_COLORS: Record<ProposalStatus, string> = {
  voting: "#3b82f6",
  pending_approval: "#f59e0b",
  returned: "#ef4444",
  approved: "#10b981",
  rejected: "#9ca3af",
  withdrawn: "#6b7280",
};

export const ACTIVITY_TYPE_LABELS: Record<ActivityType, string> = {
  competition: "比赛",
  training: "培训",
  project: "项目",
  sharing: "分享",
  event: "活动",
};

export const FEEDBACK_CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  suggestion: "建议",
  complaint: "投诉",
  report: "举报",
  other: "其他",
};

export const VOTE_CHOICE_LABELS: Record<VoteChoice, string> = {
  approve: "赞成",
  oppose: "反对",
  abstain: "弃权",
};

export const VOTE_CHOICE_COLORS: Record<VoteChoice, string> = {
  approve: "#10b981",
  oppose: "#ef4444",
  abstain: "#6b7280",
};
