import { createRequest } from "./shared";
import type { Paginated } from "../types/pagination";

const request = createRequest("/exam_board");

export interface ExamItem {
  id: number;
  exam_date: string;
  exam_title: string;
  exam_list: string;
  created_at: string;
  updated_at: string;
}

export const examApi = {
  list: () => request("/exams/") as Promise<Paginated<ExamItem>>,
  latest: () => request("/exams/latest/") as Promise<{ status: string; data: ExamItem | null; message?: string }>,
  create: (data: { exam_date: string; exam_title: string; exam_list: string }) =>
    request("/exams/", { method: "POST", body: JSON.stringify(data) }) as Promise<ExamItem>,
  update: (id: number, data: { exam_date: string; exam_title: string; exam_list: string }) =>
    request(`/exams/${id}/`, { method: "PUT", body: JSON.stringify(data) }) as Promise<ExamItem>,
};
