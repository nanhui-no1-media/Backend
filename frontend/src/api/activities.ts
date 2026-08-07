import { createRequest } from "./shared";
import type {
  ActivityDetail,
  ActivityListItem,
  ActivityFormData,
} from "../types/activities";

const request = createRequest("/activities");

export interface ActivityListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ActivityListItem[];
}

export const activityApi = {
  list: (params?: Record<string, string>): Promise<ActivityListResponse> => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/activities/${qs}`);
  },
  get: (id: number): Promise<ActivityDetail> => request(`/activities/${id}/`),
  create: (data: ActivityFormData): Promise<ActivityDetail> =>
    request("/activities/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>): Promise<ActivityDetail> =>
    request(`/activities/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  remove: (id: number) => request(`/activities/${id}/`, { method: "DELETE" }),

  // 众议投票（option_ids：选 1..K 项）
  vote: (id: number, optionIds: number[]): Promise<ActivityDetail> =>
    request(`/activities/${id}/vote/`, {
      method: "POST",
      body: JSON.stringify({ option_ids: optionIds }),
    }),

  // 众议 / 征集：提前关闭（众议立即结算；征集收件结束进入复审）
  close: (id: number): Promise<ActivityDetail> =>
    request(`/activities/${id}/close/`, { method: "POST" }),

  // 征集投稿（multipart：一束文件 = 一个作品，提交即锁定）
  submit: (id: number, files: File[]): Promise<ActivityDetail> => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    return request(`/activities/${id}/submit/`, { method: "POST", body: fd });
  },

  // 征集复审（录用 / 退稿）
  review: (
    id: number,
    submissionId: number,
    decision: "accepted" | "rejected",
    comment = ""
  ): Promise<ActivityDetail> =>
    request(`/activities/${id}/review_submission/`, {
      method: "POST",
      body: JSON.stringify({
        submission_id: submissionId,
        decision,
        comment,
      }),
    }),

  // 展示：策展人加展品（自上传，multipart）
  addExhibit: (id: number, files: File[], title = ""): Promise<ActivityDetail> => {
    const fd = new FormData();
    if (title) fd.append("title", title);
    for (const f of files) fd.append("files", f);
    return request(`/activities/${id}/add_exhibit/`, { method: "POST", body: fd });
  },
  // 展示：从征集一键导入全部作品（复制成展品快照）
  importFromCollection: (id: number, collectionId: number): Promise<ActivityDetail> =>
    request(`/activities/${id}/import_from_collection/`, {
      method: "POST",
      body: JSON.stringify({ collection_id: collectionId }),
    }),
  // 展示：点赞 / 点踩（三态切换：再点当前态=取消）
  rate: (id: number, exhibitId: number, choice: "like" | "dislike"): Promise<ActivityDetail> =>
    request(`/activities/${id}/rate/`, {
      method: "POST",
      body: JSON.stringify({ exhibit_id: exhibitId, choice }),
    }),

  // 正文内嵌图片上传（已验证成员）：返回 {url}
  uploadImage: (file: File): Promise<{ url: string }> => {
    const fd = new FormData();
    fd.append("image", file);
    return request("/activities/upload_image/", { method: "POST", body: fd });
  },
};
