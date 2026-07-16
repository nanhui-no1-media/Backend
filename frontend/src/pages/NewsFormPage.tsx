import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../components/AppShell";
import RichTextEditor from "../components/RichTextEditor";
import { api } from "../api/client";
import { newsApi } from "../api/news";
import { taskApi } from "../api/tasks";
import { type NewsCategory, CATEGORY_LABELS } from "../types/news";
import type { Tag } from "../types/tasks";
import "../styles/news.css";
import "../styles/form.css";

export default function NewsFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = !!id;
  const fileRef = useRef<HTMLInputElement>(null);

  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<NewsCategory>("notice");
  const [summary, setSummary] = useState("");
  const [content, setContent] = useState("");
  const [cover, setCover] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [tagIds, setTagIds] = useState<number[]>([]);
  const [featured, setFeatured] = useState(false);
  const [isPublished, setIsPublished] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(isEdit);
  // RichTextEditor 只读 content 作为初值；编辑模式异步载入后需 remount 才能回填
  const [rteKey, setRteKey] = useState(0);

  useEffect(() => {
    api.me()
      .then((d: any) => setAllowed(!!d.user?.is_info_group))
      .catch(() => setAllowed(false));
  }, []);

  useEffect(() => {
    taskApi.listTags().then((t: any) => setTags(t.results || t)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!isEdit) return;
    newsApi.get(Number(id))
      .then((n) => {
        setTitle(n.title);
        setCategory(n.category);
        setSummary(n.summary);
        setContent(n.content);
        setTagIds(n.tags.map((t) => t.id));
        setFeatured(n.featured);
        setIsPublished(n.is_published);
        setCoverPreview(n.cover_image_url);
        setRteKey((k) => k + 1);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  const onPickCover = (f: File | null) => {
    if (f && f.size > 2 * 1024 * 1024) {
      setError("封面图不能超过 2MB。");
      return;
    }
    setError("");
    setCover(f);
    setCoverPreview(f ? URL.createObjectURL(f) : null);
  };

  const toggleTag = (tid: number) =>
    setTagIds((cur) => (cur.includes(tid) ? cur.filter((x) => x !== tid) : [...cur, tid]));

  const submit = async () => {
    if (!title.trim()) { setError("请填写标题。"); return; }
    setSaving(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("title", title.trim());
      fd.append("category", category);
      fd.append("summary", summary);
      fd.append("content", content);
      fd.append("featured", String(featured));
      fd.append("is_published", String(isPublished));
      tagIds.forEach((tid) => fd.append("tag_ids", String(tid)));
      if (cover) fd.append("cover_image", cover);
      const saved = isEdit ? await newsApi.update(Number(id), fd) : await newsApi.create(fd);
      navigate(`/news/${saved.id}`);
    } catch (e: any) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (allowed === null || loading) {
    return <AppShell><div className="container"><p className="news-empty">加载中…</p></div></AppShell>;
  }
  if (!allowed) {
    return (
      <AppShell>
        <div className="container" style={{ paddingTop: "var(--s-10)" }}>
          <div className="alert alert-warning">仅「信息组」成员可发布与编辑新闻。</div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/news"); }}>新闻</a>
            <span className="sep">/</span>
            <span>{isEdit ? "编辑" : "撰写"}</span>
          </nav>
          <h1>{isEdit ? "编辑新闻" : "撰写新闻"}</h1>
          <p className="section-sub">{isEdit ? "修改新闻内容、封面与发布状态。" : "为社团发布一篇新闻或公告。"}</p>
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        <div className="card card-pad form-card">
          <div className="form-stack">
            {error && <div className="alert alert-danger">{error}</div>}

            <div className="field">
              <label className="label" htmlFor="nf-title">标题</label>
              <input id="nf-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)}
                     placeholder="新闻标题（最多 200 字）" maxLength={200} />
            </div>

            <div className="form-grid">
              <div className="field">
                <label className="label" htmlFor="nf-cat">分类</label>
                <select id="nf-cat" className="select" value={category}
                        onChange={(e) => setCategory(e.target.value as NewsCategory)}>
                  {(Object.keys(CATEGORY_LABELS) as NewsCategory[]).map((c) => (
                    <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="label">发布状态</label>
                <div className="seg" role="tablist" aria-label="发布状态">
                  <button className="seg-btn" type="button" aria-selected={isPublished} onClick={() => setIsPublished(true)}>发布</button>
                  <button className="seg-btn" type="button" aria-selected={!isPublished} onClick={() => setIsPublished(false)}>草稿</button>
                </div>
              </div>
            </div>

            <div className="field">
              <label className="label" htmlFor="nf-summary">摘要</label>
              <input id="nf-summary" className="input" value={summary} onChange={(e) => setSummary(e.target.value)}
                     placeholder="一句话摘要（列表/分享时展示，最多 280 字）" maxLength={280} />
            </div>

            <div className="field">
              <label className="label">封面图</label>
              <div className="avatar-upload">
                <div className={coverPreview ? "" : "ph-img"}
                     style={{ width: 160, height: 90, borderRadius: "var(--r-md)", overflow: "hidden", cursor: "pointer", flexShrink: 0 }}
                     role="button" tabIndex={0}
                     onClick={() => fileRef.current?.click()}>
                  {coverPreview
                    ? <img src={coverPreview} alt="封面预览" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    : <span className="ph-label">点击上传封面</span>}
                </div>
                <div className="au-meta">
                  <span className="au-name">封面（可选）</span>
                  <span className="au-hint">建议 16:10，JPG/PNG/WebP，≤2MB</span>
                  <span style={{ display: "flex", gap: "var(--s-2)" }}>
                    <button className="btn btn-secondary btn-sm" type="button" onClick={() => fileRef.current?.click()}>
                      {coverPreview ? "更换" : "上传"}
                    </button>
                    {(cover || coverPreview) && (
                      <button className="btn btn-ghost btn-sm" type="button" onClick={() => onPickCover(null)}>移除</button>
                    )}
                  </span>
                </div>
                <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }}
                       onChange={(e) => onPickCover(e.target.files?.[0] ?? null)} />
              </div>
            </div>

            <div className="field">
              <label className="label">正文</label>
              <RichTextEditor key={rteKey} content={content} onChange={setContent} placeholder="撰写正文…" />
            </div>

            <div className="field">
              <label className="label">标签</label>
              {tags.length === 0 ? (
                <p className="form-notice">暂无可选标签，标签由社长在任务模块维护。</p>
              ) : (
                <div className="tag-cloud" style={{ position: "static" }}>
                  {tags.map((t) => (
                    <button key={t.id} type="button" className="chip" aria-pressed={tagIds.includes(t.id)}
                            onClick={() => toggleTag(t.id)}>{t.name}</button>
                  ))}
                </div>
              )}
            </div>

            <label className="check">
              <input type="checkbox" checked={featured} onChange={(e) => setFeatured(e.target.checked)} />
              {" "}设为头条（列表页顶部展示）
            </label>

            <div className="form-actions">
              <button className="btn btn-ghost" type="button" onClick={() => navigate(-1)}>取消</button>
              <button className="btn btn-primary" type="button" onClick={submit} disabled={saving}>
                {saving ? "保存中…" : isEdit ? "保存修改" : isPublished ? "发布" : "保存草稿"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
