import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { activityApi } from "../api/activities";
import {
  ActivityDetail,
  ActivityListItem,
  ACTIVITY_TYPE_META,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_BADGE_CLASS,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_BADGE_CLASS,
} from "../types/activities";
import type { Attachment } from "../types/tasks";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";

interface CurrentUser {
  id: number;
  can_review_collections?: boolean;
  can_change_activity?: boolean;
}

export default function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activity, setActivity] = useState<ActivityDetail | null>(null);
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // 众议投票临时选择
  const [selected, setSelected] = useState<number[]>([]);
  // 征集投稿文件
  const [files, setFiles] = useState<File[]>([]);
  // 征集复审评语（按 submission id）
  const [comments, setComments] = useState<Record<number, string>>({});
  // 展示策展：加展品 / 导入征集
  const [exFiles, setExFiles] = useState<File[]>([]);
  const [exTitle, setExTitle] = useState("");
  const [myCollections, setMyCollections] = useState<ActivityListItem[]>([]);
  const [importId, setImportId] = useState<number | "">("");

  useEffect(() => {
    api.me().then((d) => setUser({ id: d.user.id, can_review_collections: d.user.permissions?.can_review_collections, can_change_activity: d.user.permissions?.can_change_activity })).catch(() => setUser(null));
  }, []);

  // 展示策展人：拉取自己的征集，供「从征集导入」选择
  useEffect(() => {
    if (activity?.type === "exhibition" && user && (activity.creator?.id === user.id || !!user.can_change_activity)) {
      activityApi.list({ type: "collection", creator: String(user.id) })
        .then((d) => setMyCollections(d.results || [])).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activity, user]);

  const load = () => {
    if (!id) return;
    activityApi.get(Number(id))
      .then((a) => { setActivity(a); setSelected(a.my_selections ?? []); })
      .catch((err) => setError(err.message));
  };
  useEffect(load, [id]);

  if (error) return <AppShell><div className="container" style={{ padding: "var(--s-16)" }}><div className="alert alert-danger"><span>{error}</span></div></div></AppShell>;
  if (!activity) return <AppShell><div className="container" style={{ padding: "var(--s-16)" }}><p className="muted">加载中…</p></div></AppShell>;

  const a = activity;
  const isOwner = !!user && a.creator?.id === user.id;
  const isReviewer = !!user && (!!user.can_review_collections || isOwner);
  const canManage = !!user && (isOwner || !!user.can_change_activity);
  const isDeliberation = a.type === "deliberation";
  const isCollection = a.type === "collection";
  const isExhibition = a.type === "exhibition";
  const total = a.total_ballots ?? 0;

  // 时间线阶段（stepper）：待开始(若有 start_at) → 开放态 → …；当前阶段高亮
  const fmtTime = (d: string | null) =>
    d ? new Date(d).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null;
  const phases = (() => {
    if (isDeliberation || isExhibition) {
      const ns = [];
      if (a.start_at) ns.push({ key: "scheduled", label: "待开始", time: fmtTime(a.start_at) });
      ns.push({ key: "open", label: isExhibition ? "展示中" : "投票中", time: a.start_at ? null : fmtTime(a.created_at) });
      ns.push({ key: "closed", label: "已结束", time: fmtTime(a.end_at) });
      return ns;
    }
    const ns = [];
    if (a.start_at) ns.push({ key: "scheduled", label: "待开始", time: fmtTime(a.start_at) });
    ns.push({ key: "collecting", label: "收件中", time: a.start_at ? null : fmtTime(a.created_at) });
    if (a.review_enabled) {
      ns.push({ key: "reviewing", label: "复审中", time: fmtTime(a.end_at) });
      ns.push({ key: "archived", label: "已归档", time: null });
    } else {
      // #51：未启用复审——收件结束直接归档，跳过复审阶段
      ns.push({ key: "archived", label: "已归档", time: fmtTime(a.end_at) });
    }
    return ns;
  })();
  const currentIndex = Math.max(0, phases.findIndex((p) => p.key === a.status));

  // 当前阶段的时间进度（0..1）：scheduled=创建→start；open/collecting=start→end；复审/归档不计。
  const nowMs = Date.now();
  const t = (iso: string | null) => (iso ? new Date(iso).getTime() : null);
  let currentProgress = 0;
  if (a.status === "scheduled" && a.start_at) {
    const s = t(a.created_at), e = t(a.start_at);
    currentProgress = s && e && e > s ? (nowMs - s) / (e - s) : 0;
  } else if (a.status === "open" || a.status === "collecting") {
    const s = a.start_at ? t(a.start_at) : t(a.created_at), e = t(a.end_at);
    currentProgress = s && e && e > s ? (nowMs - s) / (e - s) : 0;
  }
  currentProgress = Math.max(0, Math.min(1, currentProgress));

  const toggleOption = (oid: number) => {
    setSelected((cur) => {
      // 已选 → 撤选（提交前可改）
      if (cur.includes(oid)) return cur.filter((x) => x !== oid);
      // 单选（K=1）：点新的即换选（替换）
      if (a.max_choices_per_voter === 1) return [oid];
      // 多选：不超过 K
      if (cur.length >= a.max_choices_per_voter) return cur;
      return [...cur, oid];
    });
  };

  const doVote = async () => {
    if (selected.length < 1) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.vote(a.id, selected)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  const doClose = async () => {
    const msg = isDeliberation
      ? "提前结束投票并结算？"
      : a.review_enabled ? "提前结束收件、进入复审？" : "提前结束收件并归档？";
    if (!window.confirm(msg)) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.close(a.id)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  const doSubmit = async () => {
    if (files.length < 1) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.submit(a.id, files)); setFiles([]); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  const doReview = async (sid: number, decision: "accepted" | "rejected") => {
    setBusy(true); setError("");
    try { setActivity(await activityApi.review(a.id, sid, decision, comments[sid] || "")); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  // 展示：策展加展品 / 导入征集 / 评分
  const doAddExhibit = async () => {
    if (exFiles.length < 1) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.addExhibit(a.id, exFiles, exTitle)); setExFiles([]); setExTitle(""); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const doImport = async () => {
    if (!importId) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.importFromCollection(a.id, Number(importId))); setImportId(""); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const doRate = async (eid: number, choice: "like" | "dislike") => {
    setBusy(true); setError("");
    try { setActivity(await activityApi.rate(a.id, eid, choice)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const renderExFile = (f: Attachment) => {
    if (f.file_type === "image") return <img key={f.id} src={f.file_url} alt={f.file_name} />;
    if (f.file_type === "video") return <video key={f.id} src={f.file_url} controls />;
    return <a key={f.id} href={f.file_url} target="_blank" rel="noreferrer" className="muted">{f.file_name}</a>;
  };

  return (
    <AppShell>
      <div className="page-head">
        <div className="container act-head-row">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动</a>
            <span className="sep">/</span>
            <span>{a.title}</span>
          </nav>
          {canManage && a.status === "scheduled" && (
            <button className="btn btn-primary btn-sm" onClick={() => navigate(`/activity/${a.id}/edit`)}>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>
              编辑
            </button>
          )}
        </div>
      </div>

      <div className="container" style={{ paddingTop: "var(--s-8)", paddingBottom: "var(--s-16)" }}>
        {error && <div className="alert alert-danger" style={{ margin: "var(--s-4) 0" }}><span>{error}</span></div>}

        <div className="card card-pad">
          <div className="pc-meta" style={{ marginBottom: 8 }}>
            <span className={"badge " + ACTIVITY_STATUS_BADGE_CLASS[a.status]}>{ACTIVITY_STATUS_LABELS[a.status]}</span>
            <span className={"act-medal " + ACTIVITY_TYPE_META[a.type].medal}>
              <span className="act-medal-ico">{ACTIVITY_TYPE_META[a.type].emoji}</span>
              {ACTIVITY_TYPE_META[a.type].label}
            </span>
          </div>
          <h1 style={{ margin: "0 0 var(--s-4)" }}>{a.title}</h1>
          {a.body && <div className="prose" dangerouslySetInnerHTML={{ __html: a.body }} />}
          {canManage && (a.status === "open" || a.status === "collecting") && (
            <div style={{ marginTop: "var(--s-4)" }}>
              <button className="btn btn-ghost btn-sm" onClick={doClose} disabled={busy}>
                {isDeliberation ? "提前结束投票" : "提前结束收件"}
              </button>
            </div>
          )}
        </div>

        {/* 时间线（横向 stepper） */}
        <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
          <h3 className="section-h">时间线</h3>
          <div className="act-stepper">
            {phases.map((p, i) => (
              <div
                key={p.key}
                className={"act-step" + (i === currentIndex ? " is-current" : "") + (i < currentIndex ? " is-done" : "")}
                style={i === currentIndex ? ({ ["--step-progress" as any]: `${Math.round(currentProgress * 100)}%` }) : undefined}
              >
                <div className="act-step-dot">{i < currentIndex ? "✓" : i + 1}</div>
                <div className="act-step-label">{p.label}</div>
                {p.time && <div className="act-step-time">{p.time}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* 众议 / 展示(启用投票时)：投票 + 结果 */}
        {(isDeliberation || (isExhibition && (a.options?.length ?? 0) > 0)) && (
          <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
            <h3 className="section-h">投票</h3>
            {a.status === "open" && a.my_selections === null ? (
              <>
                <div className="hint" style={{ marginBottom: 8 }}>
                  可选 {a.max_choices_per_voter} 项（{a.max_choices_per_voter === 1 ? "一人一票" : "一人多票"}）；一经投出不可更改。
                </div>
                {a.options.map((o) => {
                  const on = selected.includes(o.id);
                  return (
                    <label key={o.id} className={"vote-opt" + (on ? " is-on" : "")}>
                      <input
                        type={a.max_choices_per_voter === 1 ? "radio" : "checkbox"}
                        name="vote"
                        checked={on}
                        onChange={() => toggleOption(o.id)}
                      />
                      <span className="vote-opt-text">{o.text}</span>
                    </label>
                  );
                })}
                <button className="btn btn-primary btn-sm" onClick={doVote} disabled={busy || selected.length < 1}>投票</button>
              </>
            ) : (
              <>
                {a.my_selections !== null && (
                  <div className="hint" style={{ marginBottom: 8 }}>
                    你投了：{a.my_selections.map((oid) => a.options.find((o) => o.id === oid)?.text).filter(Boolean).join("、")}
                  </div>
                )}
                <div style={{ marginTop: 8 }}>
                  {a.options.map((o) => {
                    const pct = total > 0 ? Math.round((o.vote_count / total) * 100) : 0;
                    return (
                      <div key={o.id} style={{ marginBottom: 12 }}>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <span>{o.text}</span>
                          <span className="muted">{o.vote_count} 票 · {pct}%</span>
                        </div>
                        <div style={{ height: 8, background: "#e5e7eb", borderRadius: 4, overflow: "hidden", marginTop: 4 }}>
                          <div style={{ width: `${pct}%`, height: "100%", background: "#2563eb" }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="muted" style={{ marginTop: 8 }}>共 {total} 人投票</div>

                {a.ballots === null ? (
                  <div className="alert alert-info" style={{ marginTop: 12 }}>
                    <span>秘密投票 —— 个人投票明细不公开。</span>
                  </div>
                ) : (
                  a.ballots.length > 0 && (
                    <details style={{ marginTop: 12 }}>
                      <summary className="muted">查看投票明细（{a.ballots.length}）</summary>
                      <ul style={{ marginTop: 8 }}>
                        {a.ballots.map((b) => (
                          <li key={b.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0" }}>
                            <Avatar user={b.voter} />
                            <span>{b.voter.nickname || b.voter.username}</span>
                            <span className="muted">投：{b.option_ids.map((oid) => a.options.find((o) => o.id === oid)?.text).filter(Boolean).join("、")}</span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )
                )}
              </>
            )}
          </div>
        )}

        {/* 征集：规则置顶（左上角）+ 投稿/复审/展示（单栏） */}
        {isCollection && (
          <>
            <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
              <h3 className="section-h">征集规则</h3>
              <ul className="muted">
                <li>允许后缀：{a.allowed_extensions ? a.allowed_extensions : "不限（除可执行/脚本类）"}</li>
                <li>单文件大小上限：{a.max_file_size ? `${Math.round(a.max_file_size / 1024 / 1024)} MB` : "50 MB"}</li>
                <li>单作品文件数上限：{a.max_files_per_submission}</li>
                <li>最大征集数量：{a.max_submissions ?? "不限"}{a.max_submissions && a.submissions ? `（已收 ${a.submissions.length}）` : ""}</li>
              </ul>
            </div>

            {a.status === "collecting" && !a.my_submission && (
              <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
                <h3 className="section-h">提交作品</h3>
                <div className="hint" style={{ marginBottom: 8 }}>一人一作品，提交即锁定。</div>
                <input type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files || []))} />
                {files.length > 0 && <div className="hint">已选 {files.length} 个文件</div>}
                <div style={{ marginTop: 8 }}>
                  <button className="btn btn-primary btn-sm" onClick={doSubmit} disabled={busy || files.length < 1}>提交作品</button>
                </div>
              </div>
            )}

            {a.my_submission && (
              <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
                <h3 className="section-h">我的作品</h3>
                <div className="pc-meta" style={{ marginBottom: 8 }}>
                  {a.review_enabled && (
                    <span className={"badge " + REVIEW_STATUS_BADGE_CLASS[a.my_submission.review_status]}>{REVIEW_STATUS_LABELS[a.my_submission.review_status]}</span>
                  )}
                </div>
                {a.my_submission.files.map((f) => (
                  <div key={f.id}><a href={f.file_url} target="_blank" rel="noreferrer">{f.file_name}</a></div>
                ))}
                {a.my_submission.review_comment && (
                  <div className="muted" style={{ marginTop: 8 }}>评语：{a.my_submission.review_comment}</div>
                )}
              </div>
            )}

            {a.submissions && a.submissions.length > 0 && (
              <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
                <h3 className="section-h">{!a.review_enabled ? "作品" : isReviewer ? "作品复审" : "录用作品"}</h3>
                {a.review_enabled && !isReviewer && <div className="hint" style={{ marginBottom: 8 }}>仅展示已录用作品。</div>}
                {a.submissions.map((s) => (
                  <div key={s.id} className="detail-section" style={{ padding: "12px 0", borderBottom: "1px solid var(--c-border)" }}>
                    <div className="pc-meta" style={{ marginBottom: 6 }}>
                      <Link to={`/u/${s.submitter.id}`}><Avatar user={s.submitter} /></Link>
                      <span>{s.submitter.nickname || s.submitter.username}</span>
                      {a.review_enabled && (
                        <span className={"badge " + REVIEW_STATUS_BADGE_CLASS[s.review_status]}>{REVIEW_STATUS_LABELS[s.review_status]}</span>
                      )}
                    </div>
                    {s.files.map((f) => (
                      <div key={f.id}><a href={f.file_url} target="_blank" rel="noreferrer">{f.file_name}</a></div>
                    ))}
                    {s.review_comment && <div className="muted" style={{ marginTop: 4 }}>评语：{s.review_comment}</div>}
                    {a.review_enabled && isReviewer && (a.status === "collecting" || a.status === "reviewing") && s.review_status === "pending" && (
                      <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                        <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="评语（选填）" value={comments[s.id] || ""} onChange={(e) => setComments((c) => ({ ...c, [s.id]: e.target.value }))} />
                        <button className="btn btn-success btn-sm" onClick={() => doReview(s.id, "accepted")} disabled={busy}>录用</button>
                        <button className="btn btn-ghost btn-sm" onClick={() => doReview(s.id, "rejected")} disabled={busy}>退稿</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* 展示：策展 + 展品画廊（可选投票复用上方投票块） */}
        {isExhibition && (
          <>
            {canManage && a.status !== "closed" && (
              <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
                <h3 className="section-h">策展</h3>
                <div className="field">
                  <label className="label">加展品（自上传）</label>
                  <input className="input" type="text" placeholder="展品标题（选填）" value={exTitle} onChange={(e) => setExTitle(e.target.value)} />
                  <input type="file" multiple onChange={(e) => setExFiles(Array.from(e.target.files || []))} />
                  {exFiles.length > 0 && <div className="hint">已选 {exFiles.length} 个文件</div>}
                  <div style={{ marginTop: 8 }}>
                    <button className="btn btn-primary btn-sm" onClick={doAddExhibit} disabled={busy || exFiles.length < 1}>上传展品</button>
                  </div>
                </div>
                {myCollections.length > 0 && (
                  <div className="field">
                    <label className="label">从征集导入（全部作品 → 展品快照）</label>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <select className="select" value={importId} onChange={(e) => setImportId(e.target.value ? Number(e.target.value) : "")}>
                        <option value="">选择征集…</option>
                        {myCollections.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
                      </select>
                      <button className="btn btn-ghost btn-sm" onClick={doImport} disabled={busy || !importId}>导入</button>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
              <h3 className="section-h">展品 ({a.exhibits?.length || 0})</h3>
              {a.exhibits && a.exhibits.length > 0 ? (
                <div className="exhibit-grid">
                  {a.exhibits.map((ex) => (
                    <div key={ex.id} className="exhibit-card">
                      <div className="exhibit-media">
                        {ex.files.map(renderExFile)}
                      </div>
                      <div className="exhibit-title">{ex.title || ex.submitter?.nickname || ex.submitter?.username || "未命名"}</div>
                      <div className="exhibit-rate">
                        <button className={"rate-btn" + (ex.my_rating === "like" ? " is-on like" : "")} onClick={() => doRate(ex.id, "like")} disabled={busy || a.status !== "open"}>👍 {ex.like_count}</button>
                        <button className={"rate-btn" + (ex.my_rating === "dislike" ? " is-on dislike" : "")} onClick={() => doRate(ex.id, "dislike")} disabled={busy || a.status !== "open"}>👎 {ex.dislike_count}</button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-text">暂无展品{canManage ? "，用上方「加展品」或「从征集导入」添加。" : "。"}</p>
              )}
            </div>
          </>
        )}

        {a.creator && (
          <div className="act-author">
            <Link to={`/u/${a.creator.id}`}><Avatar user={a.creator} size="md" /></Link>
            <div>
              <div className="ac-name">{a.creator.nickname || a.creator.username}</div>
              <div className="ac-desc">@{a.creator.username} · 活动发起人</div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
