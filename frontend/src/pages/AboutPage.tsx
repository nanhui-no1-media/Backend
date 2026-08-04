import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import RichTextEditor from "../components/RichTextEditor";
import { api } from "../api/client";
import { aboutApi, type AboutPage as AboutPageData } from "../api/about";
import { newsApi } from "../api/news";
import "../styles/detail.css";

export default function AboutPage() {
  const navigate = useNavigate();
  const [about, setAbout] = useState<AboutPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [canEdit, setCanEdit] = useState(false);

  // 编辑态草稿（与已保存内容分离，取消可回退）
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    aboutApi.get()
      .then(setAbout)
      .catch((e) => setError(e?.message || "加载失败"))
      .finally(() => setLoading(false));
    api.me()
      .then((d: any) => setCanEdit(!!d.user?.permissions?.can_edit_about))
      .catch(() => setCanEdit(false));
  }, []);

  const startEdit = () => {
    setDraftTitle(about?.title ?? "关于我们");
    setDraftContent(about?.content ?? "");
    setSaveError("");
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError("");
    try {
      const updated = await aboutApi.update({
        title: draftTitle.trim() || "关于我们",
        content: draftContent,
      });
      setAbout(updated);
      setEditing(false);
    } catch (e: any) {
      setSaveError(e?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <AppShell><div className="container detail-container"><p className="empty-text">加载中…</p></div></AppShell>;
  }
  if (error && !about) {
    return <AppShell><div className="container detail-container"><div className="alert alert-danger">{error}</div></div></AppShell>;
  }

  const title = about?.title || "关于我们";

  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>{title}</span>
          </nav>
          <div className="detail-head-row">
            <div className="detail-head-main">
              <h1 className="detail-title">{title}</h1>
            </div>
            {canEdit && !editing && (
              <div className="detail-head-actions">
                <button className="btn btn-ghost btn-sm" onClick={startEdit}>编辑</button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="container detail-container detail-body">
        {!editing ? (
          <div className="card card-pad detail-section">
            {about?.content ? (
              <RichTextEditor key="read" content={about.content} editable={false} />
            ) : (
              <p className="empty-text">
                {canEdit ? "尚未填写内容，点击右上「编辑」开始。" : "内容即将上线。"}
              </p>
            )}
            {about?.updated_at && (
              <p className="detail-sub">最近更新：{new Date(about.updated_at).toLocaleDateString("zh-CN")}</p>
            )}
          </div>
        ) : (
          <div className="card card-pad detail-section">
            <h3 className="section-h">标题</h3>
            <input
              className="input"
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              placeholder="关于我们"
              style={{ width: "100%" }}
            />
            <h3 className="section-h" style={{ marginTop: "var(--s-5)" }}>正文</h3>
            <RichTextEditor
              key="edit"
              content={draftContent}
              onChange={setDraftContent}
              imageUpload={(f: File) => newsApi.uploadImage(f).then((d) => d.url)}
              iframeEmbed
              minHeight={480}
            />
            {saveError && (
              <div className="alert alert-danger" style={{ marginTop: "var(--s-3)" }}>{saveError}</div>
            )}
            <div className="detail-row" style={{ marginTop: "var(--s-4)" }}>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? "保存中…" : "保存"}
              </button>
              <button className="btn btn-ghost" onClick={() => setEditing(false)} disabled={saving}>取消</button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
