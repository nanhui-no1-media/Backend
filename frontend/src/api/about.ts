import { createRequest } from "./shared";

const request = createRequest("/about");

export interface AboutPage {
  title: string;
  content: string;
  updated_at: string;
}

// 关于页单例：公开 GET / 授权 PUT（需 about.change_aboutpage）。
export const aboutApi = {
  get: () => request("/") as Promise<AboutPage>,
  update: (data: { title: string; content: string }) =>
    request("/", { method: "PUT", body: JSON.stringify(data) }) as Promise<AboutPage>,
};
