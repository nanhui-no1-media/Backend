import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { activityApi } from "../api/activities";
import {
  ActivityDetail,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_BADGE_CLASS,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_BADGE_CLASS,
} from "../types/activities";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";

interface CurrentUser {
  id: number;
  can_review_collections?: boolean;
  can_change_proposals?: boolean;
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

  useEffect(() => {
    api.me().then((d) => setUser({ id: d.user.id, can_review_collections: d.user.permissions?.can_review_collections, can_change_proposals: d.user.permissions?.can_change_proposals })).catch(() => setUser(null));
  }, []);

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
  const canManage = !!user && (isOwner || !!user.can_change_proposals);
  const isDeliberation = a.type === "deliberation";
  const isCollection = a.type === "collection";
  const total = a.total_ballots ?? 0;

  const toggleOption = (oid: number) => {
    setSelected((cur) => {
      if (cur.includes(oid)) return cur.filter((x) => x !== oid);
      if (cur.length >= a.max_choices_per_voter) return cur; // 不超过 K
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
    if (!window.confirm(isDeliberation ? "提前结束投票并结算？" : "提前结束收件、进入复审？")) return;
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

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动</a>
            <span className="sep">/</span>
            <span>{a.title}</span>
          </nav>
        </div>
      </div>

      <div className="container" style={{ maxWidth: 900, paddingBottom: "var(--s-16)" }}>
        {error && <div className="alert alert-danger" style={{ margin: "var(--s-4) 0" }}><span>{error}</span></div>}

        <div className="card card-pad">
          <div className="pc-meta" style={{ marginBottom: 8 }}>
            <span className={"badge " + ACTIVITY_STATUS_BADGE_CLASS[a.status]}>{ACTIVITY_STATUS_LABELS[a.status]}</span>
            <span className="type-tag">{ACTIVITY_TYPE_LABELS[a.type]}</span>
            {a.creator && (
              <span className="who"><Link to={`/u/${a.creator.id}`}><Avatar user={a.creator} /></Link>{a.creator.nickname || a.creator.username}</span>
            )}
            {a.end_at && <span>截止 {new Date(a.end_at).toLocaleString("zh-CN")}</span>}
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

        {/* 众议：投票 + 结果 */}
        {isDeliberation && (
          <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
            <h3 className="section-h">投票</h3>
            {a.status === "open" && a.my_selections === null ? (
              <>
                <div className="hint" style={{ marginBottom: 8 }}>
                  可选 {a.max_choices_per_voter} 项（{a.max_choices_per_voter === 1 ? "一人一票" : "一人多票"}）；一经投出不可更改。
                </div>
                {a.options.map((o) => (
                  <label key={o.id} className="fb-attrib" style={{ display: "flex", gap: 8, padding: "8px 0" }}>
                    <input
                      type={a.max_choices_per_voter === 1 ? "radio" : "checkbox"}
                      name="vote"
                      checked={selected.includes(o.id)}
                      onChange={() => toggleOption(o.id)}
                    />
                    <span>{o.text}</span>
                  </label>
                ))}
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

        {/* 征集：投稿 + 复审 + 展示 */}
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

              {a.status === "collecting" && !a.my_submission && (
                <div style={{ marginTop: "var(--s-4)" }}>
                  <label className="label">提交作品（一人一作品，提交即锁定）</label>
                  <input type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files || []))} />
                  {files.length > 0 && <div className="hint">已选 {files.length} 个文件</div>}
                  <div style={{ marginTop: 8 }}>
                    <button className="btn btn-primary btn-sm" onClick={doSubmit} disabled={busy || files.length < 1}>提交作品</button>
                  </div>
                </div>
              )}
            </div>

            {a.my_submission && (
              <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
                <h3 className="section-h">我的作品</h3>
                <div className="pc-meta" style={{ marginBottom: 8 }}>
                  <span className={"badge " + REVIEW_STATUS_BADGE_CLASS[a.my_submission.review_status]}>{REVIEW_STATUS_LABELS[a.my_submission.review_status]}</span>
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
                <h3 className="section-h">{isReviewer ? "作品复审" : "录用作品"}</h3>
                {!isReviewer && <div className="hint" style={{ marginBottom: 8 }}>仅展示已录用作品。</div>}
                {a.submissions.map((s) => (
                  <div key={s.id} className="detail-section" style={{ padding: "12px 0", borderBottom: "1px solid var(--c-border)" }}>
                    <div className="pc-meta" style={{ marginBottom: 6 }}>
                      <Link to={`/u/${s.submitter.id}`}><Avatar user={s.submitter} /></Link>
                      <span>{s.submitter.nickname || s.submitter.username}</span>
                      <span className={"badge " + REVIEW_STATUS_BADGE_CLASS[s.review_status]}>{REVIEW_STATUS_LABELS[s.review_status]}</span>
                    </div>
                    {s.files.map((f) => (
                      <div key={f.id}><a href={f.file_url} target="_blank" rel="noreferrer">{f.file_name}</a></div>
                    ))}
                    {s.review_comment && <div className="muted" style={{ marginTop: 4 }}>评语：{s.review_comment}</div>}
                    {isReviewer && (a.status === "collecting" || a.status === "reviewing") && s.review_status === "pending" && (
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
      </div>
    </AppShell>
  );
}
