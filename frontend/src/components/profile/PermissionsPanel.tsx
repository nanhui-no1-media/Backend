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
};

export default function PermissionsPanel({ profile }: { profile: UserProfileData }) {
  const perms = profile.permissions ?? {};
  const groups = profile.groups ?? [];
  return (
    <div className="card card-pad">
      <h2 className="profile-panel-title">权限与角色</h2>
      <p className="muted" style={{ marginBottom: "var(--s-4)" }}>
        所属组：{groups.length ? groups.join("、") : "（无）"}
      </p>
      <ul className="profile-perms">
        {Object.entries(CAP_LABELS).map(([key, label]) => (
          <li key={key} className="profile-perm">
            <span>{label}</span>
            <span className={"badge " + (perms[key] ? "badge-success" : "badge-ghost")}>
              {perms[key] ? "有" : "无"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
