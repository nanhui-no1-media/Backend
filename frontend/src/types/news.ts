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

export interface NewsAttachment {
  id: number;
  file_url: string;
  file_type: "image" | "video" | "document" | "archive" | "other";
  file_name: string;
  file_size: number;
}

export interface NewsListItem {
  id: number;
  title: string;
  summary: string;
  cover_image_url: string | null;
  author: NewsAuthor;
  tags: NewsTag[];
  featured: boolean;
  views: number;
  is_published: boolean;
  review_status?: "pending" | "approved" | "rejected" | "removed" | null;
  published_at: string | null;
  created_at: string;
}

export interface NewsDetail extends NewsListItem {
  content: string;
  related: NewsListItem[];
  updated_at: string;
  attachments: NewsAttachment[];
  review_comment?: string;
}

export interface NewsFormData {
  title: string;
  summary: string;
  content: string;
  featured: boolean;
  is_published: boolean;
  tag_ids: number[];
  cover_image?: File | null;
}

export const NEWS_PAGE_SIZE = 20;
