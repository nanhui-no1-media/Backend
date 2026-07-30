import { Upload as TusUpload } from "tus-js-client";
import { createRequest, getCSRFToken } from "./shared";
import { Attachment } from "../types/tasks";

const request = createRequest("/attachments");

// 同步上传通路的单文件上限（与后端 attachments.validation.MAX_FILE_SIZE 一致）；超过则走 tus。
export const MAX_SYNC_BYTES = 50 * 1024 * 1024;

// 上传必须且只能指定一个父级（task_id 或 proposal_id 或 news_id），用联合类型在编译期固化这条后端约束。
type UploadParams = { file: File } & (
  | { taskId: number; proposalId?: undefined; newsId?: undefined }
  | { proposalId: number; taskId?: undefined; newsId?: undefined }
  | { newsId: number; taskId?: undefined; proposalId?: undefined }
);

// 大文件（>50MB 图/视频）走 tus 可续传：POST /uploads/files/ … 完成后由后端 finished 钩子
// 自动挂成统一 Attachment。parent_type/parent_id 经 Upload-Metadata 声明、创建时即校验权限。
type UploadLargeParams = {
  file: File;
  parentType: "task" | "proposal" | "news";
  parentId: number;
  onProgress?: (ratio: number) => void;
};

export const attachmentApi = {
  upload: (params: UploadParams): Promise<Attachment> => {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.taskId != null) formData.append("task_id", String(params.taskId));
    if (params.proposalId != null) formData.append("proposal_id", String(params.proposalId));
    if (params.newsId != null) formData.append("news_id", String(params.newsId));
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

  // 按大小选路：≤MAX_SYNC_BYTES 走同步（返回新建的 Attachment）、>50MB 走 tus 可续传
  // （完成时由后端 finished 钩子建附件、返回 void，调用方需重新拉取父级以拿到该附件）。
  uploadRouted: (params: {
    parentType: "task" | "proposal" | "news";
    parentId: number;
    file: File;
    onProgress?: (ratio: number) => void;
  }): Promise<Attachment | void> => {
    if (params.file.size <= MAX_SYNC_BYTES) {
      return attachmentApi.upload(
        params.parentType === "task"
          ? { taskId: params.parentId, file: params.file }
          : params.parentType === "proposal"
            ? { proposalId: params.parentId, file: params.file }
            : { newsId: params.parentId, file: params.file },
      );
    }
    return attachmentApi.uploadLarge({
      parentType: params.parentType,
      parentId: params.parentId,
      file: params.file,
      onProgress: params.onProgress,
    });
  },

  delete: (attachmentId: number): Promise<null> =>
    request(`/${attachmentId}/`, { method: "DELETE" }),
};
