// 新闻分类标签与徽章配色
export type NewsCategory = "notice" | "recap" | "work" | "inform";

export interface NewsAuthor {
  id: number;
  username: string;
  nickname: string;
  avatar: string | null;
}

export interface NewsTag {
  id: number;
  name: string;
  color: string;
  news_count?: number;
}

export interface NewsListItem {
  id: number;
  title: string;
  category: NewsCategory;
  summary: string;
  cover_image_url: string | null;
  author: NewsAuthor;
  tags: NewsTag[];
  featured: boolean;
  views: number;
  is_published: boolean;
  published_at: string | null;
  created_at: string;
}

export interface NewsDetail extends NewsListItem {
  content: string;
  related: NewsListItem[];
  updated_at: string;
}

export interface NewsFormData {
  title: string;
  category: NewsCategory;
  summary: string;
  content: string;
  featured: boolean;
  is_published: boolean;
  tag_ids: number[];
  cover_image?: File | null;
}

export const CATEGORY_LABELS: Record<NewsCategory, string> = {
  notice: "社团公告",
  recap: "活动回顾",
  work: "作品展示",
  inform: "通知",
};

// 与原型一致的分类徽章配色
export const CATEGORY_BADGE_CLASS: Record<NewsCategory, string> = {
  notice: "badge-brand",
  recap: "badge-success",
  work: "badge-warning",
  inform: "badge-warning",
};

export const NEWS_PAGE_SIZE = 20;
