import { createRequest } from "./shared";
import type { NewsDetail, NewsListItem, NewsTag } from "../types/news";

const request = createRequest("/news");

export interface NewsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: NewsListItem[];
}

// list 为分页响应；featured/hot/tags 为自定义 action，直接返回对象/数组（不分页）
export const newsApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request(`/news/${qs}`) as Promise<NewsListResponse>;
  },
  get: (id: number) => request(`/news/${id}/`) as Promise<NewsDetail>,
  create: (data: FormData) => request("/news/", { method: "POST", body: data }) as Promise<NewsDetail>,
  update: (id: number, data: FormData) => request(`/news/${id}/`, { method: "PATCH", body: data }) as Promise<NewsDetail>,
  remove: (id: number) => request(`/news/${id}/`, { method: "DELETE" }),
  featured: () => request("/news/featured/") as Promise<NewsListItem | null>,
  hot: () => request("/news/hot/") as Promise<NewsListItem[]>,
  tags: () => request("/news/tags/") as Promise<NewsTag[]>,
};
