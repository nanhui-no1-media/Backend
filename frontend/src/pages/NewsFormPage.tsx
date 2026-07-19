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

interface DraftSnap {
  title: string;
  summary: string;
  category: NewsCategory;
  content: string;
  tagIds: number[];
  featured: boolean;
  isPublished: boolean;
  savedAt: number;
}

const fmtTime = (ts: number) => {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
};

export default function NewsFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = !!id;
  const fileRef = useRef<HTMLInputElement>(null);
  // 仅「新建」模式启用本地草稿自动保存（编辑模式以服务器为单一数据源）
  const draftKey = `news-draft-${id || "new"}`;
  const draftSupported = !isEdit;
  const autosaveTimer = useRef<number | null>(null);

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
  const [chars, setChars] = useState(0);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [draftRestored, setDraftRestored] = useState(false);
  // RichTextEditor 仅消费 content 作为初值；异步载入 / 草稿恢复后需 remount 才能回填
  const [rteKey, setRteKey] = useState(0);

  // 载入：先尝试恢复本地草稿（新建模式），再异步拉取编辑目标
  useEffect(() => {
    api.me()
      .then((d: any) => setAllowed(!!d.user?.permissions?.can_manage_news))
      .catch(() => setAllowed(false));
    taskApi.listTags().then((t: any) => setTags(t.results || t)).catch(() => {});

    if (draftSupported) {
      try {
        const raw = localStorage.getItem(draftKey);
        if (raw) {
          const snap = JSON.parse(raw) as DraftSnap;
          setTitle(snap.title || "");
          setSummary(snap.summary || "");
          setCategory(snap.category || "notice");
          setContent(snap.content || "");
          setTagIds(Array.isArray(snap.tagIds) ? snap.tagIds : []);
          setFeatured(!!snap.featured);
          setIsPublished(snap.isPublished ?? true);
          setSavedAt(snap.savedAt ?? null);
          setDraftRestored(true);
          setRteKey((k) => k + 1);
        }
      } catch { /* 草稿损坏则忽略，不阻断 */ }
    }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // 自动保存（仅新建模式，防抖 800ms）
  useEffect(() => {
    if (!draftSupported) return;
    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
    autosaveTimer.current = window.setTimeout(() => {
      // 空内容不落盘，避免无意义草稿
      if (!title && !summary && !content && tagIds.length === 0) return;
      const snap: DraftSnap = {
        title, summary, category, content, tagIds, featured, isPublished,
        savedAt: Date.now(),
      };
      localStorage.setItem(draftKey, JSON.stringify(snap));
      setSavedAt(snap.savedAt);
    }, 800);
    return () => { if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, summary, category, content, tagIds, featured, isPublished]);

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

  const discardDraft = () => {
    localStorage.removeItem(draftKey);
    setTitle(""); setSummary(""); setCategory("notice"); setContent("");
    setTagIds([]); setFeatured(false); setIsPublished(true);
    setSavedAt(null); setDraftRestored(false);
    setRteKey((k) => k + 1);
  };

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
      if (draftSupported) localStorage.removeItem(draftKey);
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
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        <div className="compose">
          {draftRestored && (
            <div className="alert alert-info compose-notice">
              <span>已恢复未保存的草稿{savedAt ? `（${fmtTime(savedAt)}）` : ""}。</span>
              <button type="button" className="alert-link" onClick={discardDraft}>放弃草稿</button>
            </div>
          )}
          {error && <div className="alert alert-danger">{error}</div>}

          {/* 标题：极简大号输入，写作优先 */}
          <input
            className="compose-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="新闻标题…"
            maxLength={200}
            aria-label="标题"
          />

          {/* 元信息行：分类 / 状态 / 封面 */}
          <div className="compose-meta">
            <label className="compose-pill">
              <span className="cp-label">分类</span>
              <select className="select" value={category}
                      onChange={(e) => setCategory(e.target.value as NewsCategory)}>
                {(Object.keys(CATEGORY_LABELS) as NewsCategory[]).map((c) => (
                  <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                ))}
              </select>
            </label>

            <div className="compose-pill">
              <span className="cp-label">状态</span>
              <div className="seg seg-sm" role="tablist" aria-label="发布状态">
                <button className="seg-btn" type="button" aria-selected={isPublished} onClick={() => setIsPublished(true)}>发布</button>
                <button className="seg-btn" type="button" aria-selected={!isPublished} onClick={() => setIsPublished(false)}>草稿</button>
              </div>
            </div>

            <div className="compose-pill">
              <span className="cp-label">封面</span>
              <button type="button" className="compose-cover" onClick={() => fileRef.current?.click()}
                      title="上传封面图（建议 16:10，≤2MB）">
                {coverPreview
                  ? <img src={coverPreview} alt="封面" />
                  : <span className="cc-empty"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.5" /><path d="M21 16l-5-5L5 20" /></svg>添加封面</span>}
              </button>
              {(cover || coverPreview) && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onPickCover(null)}>移除</button>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="rte-file"
                   onChange={(e) => onPickCover(e.target.files?.[0] ?? null)} />
          </div>

          {/* 大尺寸写作区 + 黏性工具栏（图片/链接/导入Word 集成在工具栏） */}
          <RichTextEditor
            key={rteKey}
            content={content}
            onChange={setContent}
            onStats={setChars}
            minHeight={560}
            imageUpload={(f) => newsApi.uploadImage(f).then((d) => d.url)}
            wordImport
            placeholder="开始撰写正文，或从 Word 导入…"
          />

          {/* 更多设置：摘要 / 标签 / 头条 */}
          <div className="compose-extras">
            <div className="field">
              <label className="label" htmlFor="nf-summary">摘要</label>
              <input id="nf-summary" className="input" value={summary} onChange={(e) => setSummary(e.target.value)}
                     placeholder="一句话摘要（列表 / 分享时展示，最多 280 字）" maxLength={280} />
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
          </div>

          {/* 底部状态 + 操作 */}
          <div className="compose-foot">
            <div className="compose-stat">
              <span>已输入 <b className="tnum">{chars}</b> 字</span>
              {draftSupported && savedAt && (
                <span className="cs-saved">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
                  草稿已自动保存
                </span>
              )}
            </div>
            <div className="compose-actions">
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
