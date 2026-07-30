import { Upload as TusUpload } from "tus-js-client";
import { createRequest, getCSRFToken } from "./shared";
import { Attachment } from "../types/tasks";

const request = createRequest("/attachments");

// 上传必须且只能指定一个父级（task_id 或 proposal_id），用联合类型在编译期固化这条后端约束。
type UploadParams = { file: File } & (
  | { taskId: number; proposalId?: undefined }
  | { proposalId: number; taskId?: undefined }
);

// 大文件（>50MB 图/视频）走 tus 可续传：POST /uploads/files/ … 完成后由后端 finished 钩子
// 自动挂成统一 Attachment。parent_type/parent_id 经 Upload-Metadata 声明、创建时即校验权限。
type UploadLargeParams = {
  file: File;
  parentType: "task" | "proposal";
  parentId: number;
  onProgress?: (ratio: number) => void;
};

export const attachmentApi = {
  upload: (params: UploadParams): Promise<Attachment> => {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.taskId != null) formData.append("task_id", String(params.taskId));
    if (params.proposalId != null) formData.append("proposal_id", String(params.proposalId));
    return request("/", { method: "POST", body: formData });
  },

  uploadLarge: (params: UploadLargeParams): Promise<void> =>
    new Promise((resolve, reject) => {
      const upload = new TusUpload(params.file, {
        endpoint: "/uploads/files/",
        retryDelays: [0, 1000, 3000, 5000],
        metadata: {
          filename: params.file.name,
          filetype: params.file.type,
          parent_type: params.parentType,
          parent_id: String(params.parentId),
        },
        headers: { "X-CSRFToken": getCSRFToken() },
        onError: (err) => reject(err),
        onProgress: (uploaded, total) => params.onProgress?.(total ? uploaded / total : 0),
        onSuccess: () => resolve(),
      });
      upload.start();
    }),

  delete: (attachmentId: number): Promise<null> =>
    request(`/${attachmentId}/`, { method: "DELETE" }),
};
