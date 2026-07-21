import { useEffect, useState } from "react";
import { api } from "../../api/client";
import "../../styles/form.css";

interface SessionRow {
  id: number;
  device_name: string;
  device_type: string;
  ip_address: string | null;
  created_at: string;
  is_current: boolean;
}

const DEVICE_TYPE_LABEL: Record<string, string> = {
  Desktop: "桌面端", Mobile: "手机", Tablet: "平板", Bot: "爬虫", Unknown: "未知",
};

const fmt = (iso: string): string => {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

export default function SessionsPanel() {
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);

  useEffect(() => {
    api.listSessions()
      .then((d: any) => setSessions(d.results))
      .catch(() => setSessions([]));
  }, []);

  return (
    <div className="card card-pad">
      <h2 className="profile-panel-title">登录记录</h2>
      {sessions === null ? (
        <p className="muted">加载中…</p>
      ) : sessions.length === 0 ? (
        <p className="muted">暂无登录记录</p>
      ) : (
        <ul className="profile-sessions">
          {sessions.map((s) => (
            <li key={s.id} className="profile-session">
              <div>
                <div className="ps-name">{s.device_name || "未知设备"}</div>
                <div className="muted ps-sub">
                  {DEVICE_TYPE_LABEL[s.device_type] ?? s.device_type}
                  {s.ip_address ? ` · ${s.ip_address}` : ""}
                  {" · " + fmt(s.created_at)}
                </div>
              </div>
              {s.is_current && <span className="badge badge-success">当前本机</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
