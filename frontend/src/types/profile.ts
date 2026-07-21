export type RoleVariant = "president" | "info" | "member";

export interface UserProfileData {
  user: { id: number; username: string; date_joined: string; email?: string };
  profile: {
    avatar: string | null;
    nickname: string;
    bio: string;
    birthday?: string | null;
    gender?: string;
  };
  role: { label: string; variant: RoleVariant };
  viewer: { is_owner: boolean; is_admin: boolean };
  permissions?: Record<string, boolean>;
  groups?: string[];
}

export type ContentType = "news" | "proposals" | "tasks";

export interface ContentItem {
  id: number;
  title: string;
  created_at?: string;
  published_at?: string;
  category?: string;
  cover_image?: string | null;
  is_published?: boolean;
  proposal_type?: string;
  status?: string;
  priority?: string;
}

/** 角色 variant → 徽章 CSS 类（配色在 styles/profile.css） */
export const ROLE_BADGE: Record<RoleVariant, string> = {
  president: "badge-role-president",
  info: "badge-role-info",
  member: "badge-role-member",
};
