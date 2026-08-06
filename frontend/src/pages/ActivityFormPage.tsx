import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { activityApi } from "../api/activities";
import RichTextEditor from "../components/RichTextEditor";
import AppShell from "../components/AppShell";
import { api } from "../api/client";
import type { ActivityType } from "../types/activities";
import "../styles/form.css";

// 默认截止时间：当前 + N 天，格式 datetime-local 取值（yyyy-MM-ddThh:mm）
function defaultEnd(days: number): string {
  const d = new Date(Date.now() + days * 86400000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function toIso(local: string): string | undefined {
  if (!local) return undefined;
  const t = new Date(local);
  return isNaN(t.getTime()) ? undefined : t.toISOString();
}

export default function ActivityFormPage() {
  const navigate = useNavigate();
  const [type, setType] = useState<ActivityType>("deliberation");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [endAt, setEndAt] = useState(defaultEnd(3));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // 众议字段
  const [options, setOptions] = useState<string[]>(["", ""]);
  const [k, setK] = useState(1);
  const [secret, setSecret] = useState(false);

  // 征集字段
  const [allowedExt, setAllowedExt] = useState(""); // 逗号分隔，空=不限
  const [maxSize, setMaxSize] = useState<string>(""); // MB，空=用全局 50MB
  const [maxFiles, setMaxFiles] = useState(5);
  const [maxSub, setMaxSub] = useState<string>(""); // 空=不限

  const switchType = (t: ActivityType) => {
    setType(t);
    setEndAt(defaultEnd(t === "deliberation" ? 3 : 7));
  };

  const setOption = (i: number, v: string) =>
    setOptions((opts) => opts.map((o, idx) => (idx === i ? v : o)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!title.trim()) {
      setError("请填写标题");
      return;
    }
    if (type === "deliberation") {
      const texts = options.map((o) => o.trim()).filter(Boolean);
      if (texts.length < 2) {
        setError("众议至少需要 2 个选项");
        return;
      }
      if (k < 1 || k > texts.length) {
        setError(`每人最多选几项须在 1..${texts.length} 之间`);
        return;
      }
    } else {
      if (maxFiles < 1) {
        setError("单作品文件数上限至少为 1");
        return;
      }
    }

    setSubmitting(true);
    try {
      let created;
      if (type === "deliberation") {
        created = await activityApi.create({
          type: "deliberation",
          title: title.trim(),
          body,
          max_choices_per_voter: k,
          is_secret_ballot: secret,
          end_at: toIso(endAt),
          option_texts: options.map((o) => o.trim()).filter(Boolean),
        });
      } else {
        created = await activityApi.create({
          type: "collection",
          title: title.trim(),
          body,
          allowed_extensions: allowedExt.trim(),
          max_file_size: maxSize.trim() ? Math.round(parseFloat(maxSize) * 1024 * 1024) : null,
          max_files_per_submission: maxFiles,
          max_submissions: maxSub.trim() ? parseInt(maxSub, 10) : null,
          end_at: toIso(endAt),
        });
      }
      navigate(`/activity/${created.id}`);
    } catch (err: any) {
      setError(err.message || "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动</a>
            <span className="sep">/</span>
            <span>发起活动</span>
          </nav>
          <h1>发起活动</h1>
          <p className="section-sub">发起一场众议（投票）或征集（收作品），发起即对全体已验证成员开放。</p>
        </div>
      </div>

      <div className="container" style={{ maxWidth: 820, paddingBottom: "var(--s-16)" }}>
        {error && (
          <div className="alert alert-danger" style={{ margin: "var(--s-4) 0" }}>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={submit} className="card card-pad">
          <div className="field">
            <label className="label">类型</label>
            <div className="seg" role="tablist">
              <button type="button" className="seg-btn" aria-selected={type === "deliberation"} onClick={() => switchType("deliberation")}>众议（投票）</button>
              <button type="button" className="seg-btn" aria-selected={type === "collection"} onClick={() => switchType("collection")}>征集（收作品）</button>
            </div>
          </div>

          <div className="field">
            <label className="label">标题 <span className="hint">*</span></label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required placeholder="一句话说明" />
          </div>

          <div className="field">
            <label className="label">正文说明</label>
            <RichTextEditor
              content={body}
              onChange={setBody}
              minHeight={320}
              placeholder="背景、规则、要求……（支持图片 / iframe 嵌入）"
              imageUpload={(f) => activityApi.uploadImage(f).then((d) => d.url)}
              iframeEmbed
              wordImport
            />
          </div>

          {type === "deliberation" ? (
            <>
              <div className="field">
                <label className="label">投票选项 <span className="hint">（至少 2 个，开放即锁定）</span></label>
                {options.map((o, i) => (
                  <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                    <input className="input" value={o} onChange={(e) => setOption(i, e.target.value)} maxLength={200} placeholder={`选项 ${i + 1}`} />
                    {options.length > 2 && (
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOptions(options.filter((_, idx) => idx !== i))}>移除</button>
                    )}
                  </div>
                ))}
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOptions([...options, ""])}>+ 增加选项</button>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label className="label">每人最多选几项（K）</label>
                  <input className="input" type="number" min={1} value={k} onChange={(e) => setK(parseInt(e.target.value, 10) || 1)} />
                  <div className="hint">K=1 即一人一票；K&gt;1 即一人多票（最多选 K 项）。</div>
                </div>
                <div className="field">
                  <label className="label">投票截止</label>
                  <input className="input" type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} />
                </div>
              </div>

              <div className="field">
                <label className="fb-attrib">
                  <input type="checkbox" checked={secret} onChange={(e) => setSecret(e.target.checked)} />
                  <span>秘密投票 —— 仅聚合计数可见，个人投票明细仅超级管理员可见</span>
                </label>
              </div>
            </>
          ) : (
            <>
              <div className="form-grid">
                <div className="field">
                  <label className="label">允许后缀 <span className="hint">（逗号分隔，空=不限）</span></label>
                  <input className="input" value={allowedExt} onChange={(e) => setAllowedExt(e.target.value)} placeholder=".jpg,.png,.pdf" />
                </div>
                <div className="field">
                  <label className="label">单文件大小上限（MB） <span className="hint">（空=50MB）</span></label>
                  <input className="input" type="number" min={1} value={maxSize} onChange={(e) => setMaxSize(e.target.value)} placeholder="50" />
                </div>
              </div>
              <div className="form-grid">
                <div className="field">
                  <label className="label">单作品文件数上限</label>
                  <input className="input" type="number" min={1} value={maxFiles} onChange={(e) => setMaxFiles(parseInt(e.target.value, 10) || 1)} />
                </div>
                <div className="field">
                  <label className="label">最大征集数量 <span className="hint">（满额自动关闭；空=不限）</span></label>
                  <input className="input" type="number" min={1} value={maxSub} onChange={(e) => setMaxSub(e.target.value)} placeholder="不限" />
                </div>
              </div>
              <div className="field">
                <label className="label">收件截止</label>
                <input className="input" type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} />
              </div>
            </>
          )}

          <div style={{ display: "flex", gap: 12, marginTop: "var(--s-4)" }}>
            <button className="btn btn-primary" type="submit" disabled={submitting}>{submitting ? "提交中…" : "发起活动"}</button>
            <button className="btn btn-ghost" type="button" onClick={() => navigate("/activity")}>取消</button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
