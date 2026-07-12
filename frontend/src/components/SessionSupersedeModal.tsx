import { SupersedeTakeover } from "../api/shared";

export default function SessionSupersedeModal({
  takeover,
  onConfirm,
}: {
  takeover: SupersedeTakeover | null;
  onConfirm: () => void;
}) {
  if (!takeover) return null;

  const when = takeover.time ? new Date(takeover.time).toLocaleString("zh-CN") : "";
  const where = [takeover.device_name, takeover.ip ? `IP ${takeover.ip}` : ""]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 8,
          padding: 24,
          width: 380,
          maxWidth: "90vw",
          textAlign: "center",
          boxShadow: "0 8px 30px rgba(0,0,0,0.2)",
        }}
      >
        <h3 style={{ margin: "0 0 12px", fontSize: 18 }}>账号在其他设备登录</h3>
        <p style={{ color: "#374151", lineHeight: 1.6, margin: "0 0 8px" }}>
          您的账号{when ? `于 ${when} ` : ""}
          {where ? `在 ${where} ` : ""}登录，您已被迫下线。
        </p>
        <p style={{ color: "#6b7280", fontSize: 13, margin: "0 0 16px" }}>
          如非本人操作，请及时修改密码。
        </p>
        <button
          onClick={onConfirm}
          style={{
            padding: "8px 20px",
            background: "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          重新登录
        </button>
      </div>
    </div>
  );
}
