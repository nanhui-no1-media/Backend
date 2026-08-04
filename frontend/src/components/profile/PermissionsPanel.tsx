import type { ReactNode } from "react";
import type { UserProfileData } from "../../types/profile";
import "../../styles/form.css";

const CAP_LABELS: Record<string, string> = {
  can_manage_news: "管理新闻",
  can_manage_tasks: "管理任务",
  can_assign_task: "指派任务",
  can_manage_tags: "管理标签",
  can_approve_proposals: "审批申报",
  can_change_proposals: "修改申报",
  can_view_feedback: "查看反馈",
  can_edit_about: "编辑关于",
};

/** 统一的 24x24 线性图标外壳，沿用项目内联 SVG 约定（stroke=currentColor）。 */
function Svg({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

const CAP_ICONS: Record<string, ReactNode> = {
  can_manage_news: (
    <Svg>
      <rect x={4} y={3} width={16} height={18} rx={2} />
      <path d="M8 7h4" />
      <path d="M8 11h8" />
      <path d="M8 15h8" />
    </Svg>
  ),
  can_manage_tasks: (
    <Svg>
      <rect x={4} y={4} width={16} height={16} rx={2} />
      <path d="M8.5 12l2.5 2.5 4.5-5" />
    </Svg>
  ),
  can_assign_task: (
    <Svg>
      <circle cx={9} cy={8} r={3.2} />
      <path d="M3.5 19a5.5 5.5 0 0 1 8-4.9" />
      <path d="M15 11h5" />
      <path d="M17.5 8.5L20 11l-2.5 2.5" />
    </Svg>
  ),
  can_manage_tags: (
    <Svg>
      <path d="M3 11V4.5a1.5 1.5 0 0 1 1.5-1.5H11l8.5 8.5a1.5 1.5 0 0 1 0 2.1l-5.4 5.4a1.5 1.5 0 0 1-2.1 0z" />
      <circle cx={7.5} cy={7.5} r={1.2} />
    </Svg>
  ),
  can_approve_proposals: (
    <Svg>
      <circle cx={12} cy={12} r={8.5} />
      <path d="M8.5 12.2l2.3 2.3 4.7-5" />
    </Svg>
  ),
  can_change_proposals: (
    <Svg>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
    </Svg>
  ),
  can_view_feedback: (
    <Svg>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </Svg>
  ),
  can_edit_about: (
    <Svg>
      <circle cx={12} cy={12} r={9} />
      <path d="M12 11v5" />
      <path d="M12 7.5h.01" />
    </Svg>
  ),
};

export default function PermissionsPanel({ profile }: { profile: UserProfileData }) {
  const perms = profile.permissions ?? {};
  const groups = profile.groups ?? [];
  return (
    <div className="card card-pad">
      <h2 className="profile-panel-title">权限与角色</h2>
      <ul className="profile-perms">
        {Object.entries(CAP_LABELS).map(([key, label]) => (
          <li key={key} className="profile-perm">
            <span className="profile-perm-main">
              <span className="profile-perm-icon">{CAP_ICONS[key] ?? null}</span>
              <span>{label}</span>
            </span>
            <span className={"badge " + (perms[key] ? "badge-success" : "badge-ghost")}>
              {perms[key] ? "有" : "无"}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted" style={{ marginTop: "var(--s-4)" }}>
        所属组：{groups.length ? groups.join("、") : "（无）"}
      </p>
    </div>
  );
}
