import { createRequest } from "./shared";
import type { FeedbackFormData, ProposalDetail, ProposalListItem } from "../types/proposals";

const request = createRequest("/proposals");

export const proposalApi = {
  list: (params?: Record<string, string>): Promise<ProposalListItem[] | { results: ProposalListItem[] }> => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/proposals/${qs}`);
  },
  get: (id: number): Promise<ProposalDetail> => request(`/proposals/${id}/`),

  // 公开匿名提交反馈/举报（无需登录）
  submitFeedback: (data: FeedbackFormData): Promise<ProposalDetail> =>
    request("/proposals/submit_feedback/", { method: "POST", body: JSON.stringify(data) }),

  // 社长审批
  approve: (id: number): Promise<ProposalDetail> =>
    request(`/proposals/${id}/approve/`, { method: "POST" }),
  reject: (id: number, reason: string): Promise<ProposalDetail> =>
    request(`/proposals/${id}/reject/`, { method: "POST", body: JSON.stringify({ reason }) }),

  // 创建人撤回（待审批阶段）
  withdraw: (id: number): Promise<ProposalDetail> =>
    request(`/proposals/${id}/withdraw/`, { method: "POST" }),

  // 当前用户提交的反馈（匿名反馈无归属，不在此列）
  myProposals: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/proposals/my_proposals/${qs}`);
  },
};
