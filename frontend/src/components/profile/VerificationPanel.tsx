import { useEffect, useState } from "react";
import { api } from "../../api/client";
import "../../styles/profile.css";

// 前后端契约（#36）：通道集 + 通道对象键集，与后端 /auth/verification/ 对齐
// （accounts.tests_verification.VerificationPanelContractTest 钉死，防漂移）。
export const VERIFICATION_CHANNELS = ["email", "manual"];
export const VERIFICATION_CARD_FIELDS = ["channel", "status", "identifier", "verified_at"];

type ChannelStatus = "none" | "pending" | "approved" | "rejected";

interface ChannelCard {
  channel: string;
  status: ChannelStatus;
  identifier: string;
  verified_at: string | null;
}

interface VerificationStatus {
  is_verified: boolean;
  channels: ChannelCard[];
}

const CHANNEL_META: Record<string, { label: string; desc: string }> = {
  email: { label: "邮箱验证", desc: "绑定并验证一个邮箱即可成为已验证用户。" },
  manual: { label: "人工审批", desc: "提交身份证明，由管理员审核通过即成为已验证用户。" },
};

// 各通道各状态 → 展示文案 + 徽章 + 提示（数据驱动：加状态只改此处）。
const STATE: Record<string, Record<ChannelStatus, { label: string; badge: string; hint: string }>> = {
  email: {
    none: { label: "未绑定", badge: "badge-ghost", hint: "绑定邮箱后可用邮箱登录、找回密码。" },
    pending: { label: "待验证", badge: "badge-warning", hint: "验证邮件已发送，请查收并点击验证链接。" },
    approved: { label: "已通过", badge: "badge-success", hint: "邮箱已验证。" },
    rejected: { label: "已驳回", badge: "badge-danger", hint: "" }, // email 通道无驳回，保留数据驱动完备性
  },
  manual: {
    none: { label: "未提交", badge: "badge-ghost", hint: "提交身份证明（学生证照片等），由管理员审核。" },
    pending: { label: "审核中", badge: "badge-warning", hint: "身份证明已提交，等待管理员审核。" },
    approved: { label: "已通过", badge: "badge-success", hint: "身份审核已通过。" },
    rejected: { label: "已驳回", badge: "badge-danger", hint: "身份证明被驳回，可重新提交。" },
  },
};

export default function VerificationPanel() {
  const [data, setData] = useState<VerificationStatus | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    api.verificationStatus()
      .then((d: any) => { if (alive) setData(d as VerificationStatus); })
      .catch((e: any) => { if (alive) setErr(e.message || "加载失败"); });
    return () => { alive = false; };
  }, []);

  if (err) {
    return (
      <div className="card card-pad">
        <h2 className="profile-panel-title">账号验证</h2>
        <p className="muted">{err}</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="card card-pad">
        <h2 className="profile-panel-title">账号验证</h2>
        <p className="muted">加载中…</p>
      </div>
    );
  }

  return (
    <div className="card card-pad">
      <h2 className="profile-panel-title">账号验证</h2>
      <p className="muted verify-overview">
        {data.is_verified
          ? "你的账号已验证（用户）。"
          : "你的账号尚未验证（访客）——完成下列任一通道即成为已验证用户，解锁发帖 / 发消息 / 建申报等。"}
      </p>
      <div className="verify-cards">
        {data.channels.map((c) => {
          const meta = CHANNEL_META[c.channel] ?? { label: c.channel, desc: "" };
          const st = (STATE[c.channel] ?? STATE.manual)[c.status];
          const showPendingId = c.channel === "email" && c.status === "pending" && c.identifier;
          return (
            <div key={c.channel} className={"verify-card verify-card-" + c.status}>
              <div className="verify-card-head">
                <span className="verify-card-label">{meta.label}</span>
                <span className={"badge " + st.badge}>{st.label}</span>
              </div>
              {meta.desc && <p className="muted verify-card-desc">{meta.desc}</p>}
              {showPendingId && <p className="muted verify-card-id">待验证邮箱：{c.identifier}</p>}
              {c.channel === "email" && c.status === "approved" && c.identifier && (
                <p className="muted verify-card-id">已绑定：{c.identifier}</p>
              )}
              {st.hint && <p className="muted verify-card-hint">{st.hint}</p>}
              <div className="verify-card-actions">{/* 通道动作在 #37（邮箱）/ #38（人工）接入 */}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
