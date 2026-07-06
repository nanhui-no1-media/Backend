import { createRequest } from "./shared";
import {
  ActivityFormData,
  FeedbackFormData,
  ProposalDetail,
  ProposalListItem,
  VoteChoice,
} from "../types/proposals";

const request = createRequest("/proposals");

export const proposalApi = {
  list: (params?: Record<string, string>): Promise<ProposalListItem[] | { results: ProposalListItem[] }> => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/proposals/${qs}`);
  },
  get: (id: number): Promise<ProposalDetail> => request(`/proposals/${id}/`),
  createActivity: (data: ActivityFormData): Promise<ProposalDetail> =>
    request("/proposals/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<ActivityFormData>): Promise<ProposalDetail> =>
    request(`/proposals/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),

  // 公开匿名提交反馈/举报（无需登录）
  submitFeedback: (data: FeedbackFormData): Promise<ProposalDetail> =>
    request("/proposals/submit_feedback/", { method: "POST", body: JSON.stringify(data) }),

  // 投票（活动申报）
  vote: (id: number, voteChoice: VoteChoice): Promise<ProposalDetail> =>
    request(`/proposals/${id}/vote/`, { method: "POST", body: JSON.stringify({ vote_choice: voteChoice }) }),

  // 社长审批
  approve: (id: number): Promise<ProposalDetail> =>
    request(`/proposals/${id}/approve/`, { method: "POST" }),
  returnProposal: (id: number, reason: string): Promise<ProposalDetail> =>
    request(`/proposals/${id}/return_proposal/`, { method: "POST", body: JSON.stringify({ reason }) }),
  reject: (id: number, reason: string): Promise<ProposalDetail> =>
    request(`/proposals/${id}/reject/`, { method: "POST", body: JSON.stringify({ reason }) }),

  // 创建人：重新提交（打回后）/ 撤回
  resubmit: (id: number): Promise<ProposalDetail> =>
    request(`/proposals/${id}/resubmit/`, { method: "POST" }),
  withdraw: (id: number): Promise<ProposalDetail> =>
    request(`/proposals/${id}/withdraw/`, { method: "POST" }),

  // 附件
  addAttachment: (id: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/proposals/${id}/add_attachment/`, { method: "POST", body: formData });
  },
  deleteAttachment: (id: number, attachmentId: number) =>
    request(`/proposals/${id}/delete_attachment/`, {
      method: "POST",
      body: JSON.stringify({ attachment_id: attachmentId }),
    }),

  // 当前用户创建的活动申报
  myProposals: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/proposals/my_proposals/${qs}`);
  },
};
