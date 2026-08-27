import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import RichTextEditor from "../components/RichTextEditor";
import ArticleToc from "../components/ArticleToc";
import { api } from "../api/client";
import { recruitmentApi } from "../api/recruitment";
import { newsApi } from "../api/news";
import "../styles/detail.css";
import "../styles/form.css";

export default function JoinPage() {
  const navigate = useNavigate();
  const [content, setContent] = useState("");
  const [ack, setAck] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    document.title = "加入社团 · 南汇一中传媒社";
    recruitmentApi.landing().then((d) => {
      setContent(d.notice.content || "");
      setDraft(d.notice.content || "");
    });
    api.me()
      .then((d: any) => setCanEdit(!!d.user?.permissions?.can_edit_about))
      .catch(() => setCanEdit(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await recruitmentApi.updateNotice(draft);
      setContent(draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="page-head page-head-gap">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>加入社团</span>
          </nav>
          <div className="page-head-row">
            <h1>加入社团</h1>
            {canEdit && !editing && (
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => navigate("/join/editor")}>编辑问卷</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>编辑公告</button>
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="container detail-container page-body-gap">
        <div className="card card-pad">
          {!editing ? (
            content ? (
              <>
                <ArticleToc html={content} />
                <RichTextEditor key="n" content={content} editable={false} />
              </>
            ) : <p className="empty-text">招生公告即将发布。</p>
          ) : (
            <>
              <RichTextEditor
                key="e"
                content={draft}
                onChange={setDraft}
                imageUpload={(f: File) => newsApi.uploadImage(f).then((d) => d.url)}
                minHeight={280}
              />
              <div className="form-actions" style={{ marginTop: 12 }}>
                <button className="btn btn-ghost" onClick={() => setEditing(false)}>取消</button>
                <button className="btn btn-primary" disabled={saving} onClick={save}>保存</button>
              </div>
            </>
          )}
        </div>
        <label style={{ display: "flex", gap: 8, margin: "var(--s-5) 0", alignItems: "flex-start" }}>
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
          <span>我已阅读并知晓公告内容</span>
        </label>
        <button className="btn btn-primary btn-lg" disabled={!ack} onClick={() => {
          sessionStorage.setItem("join_notice_ack", "1");
          navigate("/join/form");
        }}>
          立即加入
        </button>
      </div>
    </AppShell>
  );
}
