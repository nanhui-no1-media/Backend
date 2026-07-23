import { createRequest } from "./shared";
import { Attachment } from "../types/tasks";

const request = createRequest("/attachments");

// 上传必须且只能指定一个父级（task_id 或 proposal_id），用联合类型在编译期固化这条后端约束。
type UploadParams = { file: File } & (
  | { taskId: number; proposalId?: undefined }
  | { proposalId: number; taskId?: undefined }
);

export const attachmentApi = {
  upload: (params: UploadParams): Promise<Attachment> => {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.taskId != null) formData.append("task_id", String(params.taskId));
    if (params.proposalId != null) formData.append("proposal_id", String(params.proposalId));
    return request("/", { method: "POST", body: formData });
  },

  delete: (attachmentId: number): Promise<null> =>
    request(`/${attachmentId}/`, { method: "DELETE" }),
};
