export type IdentityReviewStatus = "pending" | "approved" | "rejected";

export interface IdentityProofBrief {
  id: number;
  uploaded_at: string;
  url: string;
}

export interface IdentityReviewItem {
  id: number;
  user_id: number;
  username: string;
  real_name: string;
  identity: string;
  status: IdentityReviewStatus;
  verified_at: string | null;
  verified_by: { id: number; username: string } | null;
  proofs: IdentityProofBrief[];
}

export const IDENTITY_STATUS_LABELS: Record<IdentityReviewStatus, string> = {
  pending: "待审",
  approved: "已通过",
  rejected: "已驳回",
};

export const IDENTITY_STATUS_BADGE: Record<IdentityReviewStatus, string> = {
  pending: "badge-warning",
  approved: "badge-success",
  rejected: "badge-danger",
};

export const IDENTITY_LABELS: Record<string, string> = {
  student: "在校生",
  external: "外校生",
  graduate: "毕业生",
  parent: "家长",
  teacher: "教师",
};
