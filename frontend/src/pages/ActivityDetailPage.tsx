import { useState, useEffect } from "react";
import { useParams, useNavigate, Link, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { activityApi } from "../api/activities";
import {
  ActivityDetail,
  ActivityListItem,
  ACTIVITY_TYPE_META,
  AUDIENCE_LABELS,
  activityPhase,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_BADGE_CLASS,
} from "../types/activities";
import type { ActivityStatus } from "../types/activities";
import type { Attachment } from "../types/tasks";
import Avatar from "../components/Avatar";
import PageChrome from "../components/PageChrome";
import SurveyFill from "../components/SurveyFill";
import { useSitePolicy } from "../api/sitePolicy";
import { useEmbedMode } from "../embed";
import { useLoginModal } from "../components/LoginModalProvider";
import AuthorReviewBanner from "../components/AuthorReviewBanner";

interface CurrentUser {
  id: number;
  can_review_collections?: boolean;
  can_change_activity?: boolean;
}

export default function ActivityDetailPage({
  embedded,
  activityId,
}: {
  embedded?: boolean;
  activityId?: number;
} = {}) {
  const params = useParams<{ id: string }>();
  const id = activityId != null ? String(activityId) : params.id;
  const navigate = useNavigate();
  const location = useLocation();
  const { openLogin, authNonce } = useLoginModal();
  const urlEmbed = useEmbedMode();
  const embed = Boolean(embedded || urlEmbed);
  const policy = useSitePolicy();
  const syncMb = Math.round(policy.sync_upload_max_bytes / 1024 / 1024);
  const [activity, setActivity] = useState<ActivityDetail | null>(null);
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loadStatus, setLoadStatus] = useState<number>(0);
  const [busy, setBusy] = useState(false);
  const [guestSubmitted, setGuestSubmitted] = useState(false);
  const [fillKey, setFillKey] = useState(0);

  // 展示布展(策展人;待开始+展示中):手动添加 / 删 / 从征集导入(改标题仅待开始)
  const [newTitle, setNewTitle] = useState("");
  const [newFiles, setNewFiles] = useState<File[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const [collections, setCollections] = useState<ActivityListItem[]>([]);
  const [pickedCollection, setPickedCollection] = useState<number | null>(null);
  const [pickedSubs, setPickedSubs] = useState<number[]>([]);
  const [collectionDetail, setCollectionDetail] = useState<ActivityDetail | null>(null);

  // 众议投票临时选择
  const [selected, setSelected] = useState<number[]>([]);
  // 征集投稿文件
  const [files, setFiles] = useState<File[]>([]);
  // 征集复审评语（按 submission id）
  const [comments, setComments] = useState<Record<number, string>>({});
  useEffect(() => {
    api.me().then((d) => setUser({ id: d.user.id, can_review_collections: d.user.permissions?.can_review_collections, can_change_activity: d.user.permissions?.can_change_activity })).catch(() => setUser(null));
  }, [authNonce]);

  useEffect(() => {
    if (!id) return;
    setLoadError("");
    setLoadStatus(0);
    setActivity(null);
    setGuestSubmitted(false);
    activityApi.get(Number(id))
      .then((a) => { setActivity(a); setSelected(a.my_selections ?? []); })
      .catch((err: any) => {
        setLoadError(err.message || "加载失败");
        setLoadStatus(err.status || 0);
      });
  }, [id, authNonce]);

  if (!activity) {
    if (user === undefined || !loadError) {
      return <PageChrome embedded={embed}><div className="container" style={{ padding: "var(--s-16)" }}><p className="muted">加载中…</p></div></PageChrome>;
    }
    const needLogin = !embed && !user && (loadStatus === 404 || loadStatus === 403);
    return (
      <PageChrome embedded={embed}>
        <div className="container" style={{ padding: "var(--s-16)" }}>
          {needLogin ? (
            <div className="card card-pad">
              <h2 style={{ margin: "0 0 var(--s-3)" }}>需要登录</h2>
              <p className="muted" style={{ marginBottom: "var(--s-4)" }}>
                该活动仅登录成员可见。众议、征集、展示及仅成员调研需登录后查看。
              </p>
              <button className="btn btn-primary" onClick={() => openLogin(location.pathname + location.search)}>登录</button>
            </div>
          ) : (
            <div className="alert alert-danger"><span>{loadError}</span></div>
          )}
        </div>
      </PageChrome>
    );
  }

  const a = activity;
  const isOwner = !!user && a.creator?.id === user.id;
  const isReviewer = !!user && (!!user.can_review_collections || isOwner);
  const canManage = !!user && (isOwner || !!user.can_change_activity);
  const isDeliberation = a.type === "deliberation";
  const isCollection = a.type === "collection";
  const isExhibition = a.type === "exhibition";
  const isSurvey = a.type === "survey";
  const canEditSchema =
    isSurvey &&
    canManage &&
    (a.status === "scheduled" || (a.status === "open" && (a.response_count ?? 0) === 0));
  const surveyApproved = !a.review_status || a.review_status === "approved";
  const alreadySubmitted = !!user && a.my_response != null;
  const canFillSurvey =
    isSurvey &&
    a.status === "open" &&
    surveyApproved &&
    !alreadySubmitted &&
    !guestSubmitted &&
    (a.audience === "public" || !!user);
  const closeLabel = isDeliberation
    ? "提前结束投票"
    : isCollection
      ? "提前结束收件"
      : isSurvey
        ? "提前结束征答"
        : "提前结束展示";
  const closeConfirm = isDeliberation
    ? "提前结束投票并结算？"
    : isCollection
      ? (a.review_enabled ? "提前结束收件、进入复审？" : "提前结束收件并归档？")
      : isSurvey
        ? "提前结束征答？"
        : "提前结束展示并结算？";
  const owesVote = (isDeliberation && a.status === "open" && a.my_selections === null)
    || (isExhibition && a.voting_enabled && a.status === "open" && a.my_selections === null);
  const owesSubmit = isCollection && a.status === "collecting" && !a.my_submission;
  const memberDebt = owesVote || owesSubmit;
  const total = a.total_ballots ?? 0;
  // 阶段勋章：类型感知（展示 open=展示中，其余 open=投票中）
  const phase = activityPhase(a.type, a.status);

  // 时间线阶段（stepper）：待开始(若有 start_at) → 开放态 → …；当前阶段高亮
  const fmtTime = (d: string | null) =>
    d ? new Date(d).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null;
  const phases = (() => {
    if (isDeliberation || isExhibition || isSurvey) {
      const ns = [];
      if (a.start_at) ns.push({ key: "scheduled", label: "待开始", time: fmtTime(a.start_at) });
      ns.push({
        key: "open",
        label: isExhibition ? "展示中" : isSurvey ? "征答中" : "投票中",
        time: a.start_at ? null : fmtTime(a.created_at),
      });
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
    if (!window.confirm(closeConfirm)) return;
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

  // 展示：点赞 / 点踩（三态）+ 展品投票（复用 doVote，option_ids 即展品 vote_option_id）
  const doRate = async (eid: number, choice: "like" | "dislike") => {
    setBusy(true); setError("");
    try { setActivity(await activityApi.rate(a.id, eid, choice)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  // 展示布展门控:加/导入/删 → 待开始+展示中(canManageExhibits);改标题 → 仅待开始(canEditExhibit,镜像后端 can_edit_exhibit)
  const canManageExhibits = isExhibition && canManage && (a.status === "scheduled" || a.status === "open");
  const canEditExhibit = isExhibition && canManage && a.status === "scheduled";

  const doAddExhibit = async () => {
    if (newFiles.length < 1) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.addExhibit(a.id, newTitle.trim(), newFiles)); setNewTitle(""); setNewFiles([]); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const doUpdateExhibit = async (eid: number, curTitle: string) => {
    const t = window.prompt("修改展品标题（留空则不变）：", curTitle);
    if (t === null) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.updateExhibit(a.id, eid, t, null)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const doDeleteExhibit = async (eid: number) => {
    if (!window.confirm("删除该展品？")) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.deleteExhibit(a.id, eid)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const openImport = async () => {
    setImportOpen(true);
    const list = await activityApi.list({ type: "collection" });
    setCollections(list.results);
    if (list.results.length > 0) {
      setPickedCollection(list.results[0].id);
      setCollectionDetail(await activityApi.get(list.results[0].id));
    }
  };
  const pickCollection = async (cid: number) => {
    setPickedCollection(cid);
    setPickedSubs([]);
    setCollectionDetail(await activityApi.get(cid));
  };
  const doImport = async () => {
    if (pickedSubs.length < 1 || pickedCollection == null) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.importFromCollection(a.id, pickedCollection, pickedSubs)); setImportOpen(false); setPickedSubs([]); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  const renderExFile = (f: Attachment) => {
    if (f.file_type === "image") return <img key={f.id} src={f.file_url} alt={f.file_name} />;
    if (f.file_type === "video") return <video key={f.id} src={f.file_url} controls />;
    return <a key={f.id} href={f.file_url} target="_blank" rel="noreferrer" className="muted">{f.file_name}</a>;
  };

  return (
    <PageChrome embedded={embed}>
      {!embed && (
      <div className="page-head">
        <div className="container act-head-row">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动</a>
            <span className="sep">/</span>
            <span>{a.title}</span>
          </nav>
          {((canManage && a.status === "scheduled" && !memberDebt) || canEditSchema) && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {canManage && a.status === "scheduled" && !memberDebt && (
                <button className="btn btn-primary btn-sm" onClick={() => navigate(`/activity/${a.id}/edit`)}>
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>
                  编辑
                </button>
              )}
              {canEditSchema && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/activity/${a.id}/survey-edit`)}>
                  编辑问卷
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      )}

      <div className="container" style={{ paddingTop: embed ? 0 : "var(--s-8)", paddingBottom: embed ? 0 : "var(--s-16)" }}>
        {error && <div className="alert alert-danger" style={{ margin: "var(--s-4) 0" }}><span>{error}</span></div>}

        <div className="card card-pad">
          <div className="pc-meta" style={{ marginBottom: 8 }}>
            <span className={"act-medal " + phase.medalClass}>
              <span className="act-medal-ico">{phase.emoji}</span>
              {phase.label}
            </span>
            <span className={"act-medal " + ACTIVITY_TYPE_META[a.type].medal}>
              <span className="act-medal-ico">{ACTIVITY_TYPE_META[a.type].emoji}</span>
              {ACTIVITY_TYPE_META[a.type].label}
            </span>
            {isSurvey && (
              <span className={"badge " + (a.audience === "public" ? "badge-brand" : "badge-neutral")}>
                {AUDIENCE_LABELS[a.audience]}
              </span>
            )}
          </div>
          <h1 style={{ margin: "0 0 var(--s-4)" }}>{a.title}</h1>
        </div>

        {!embed && (
          <AuthorReviewBanner
            kind="activity"
            status={a.review_status}
            comment={a.review_comment}
            extra={
              a.review_status === "pending" && a.status !== "closed" && a.status !== "archived"
                ? (isSurvey
                  ? "活动会按你设的时间推进，但在审核通过前访客/成员看不到、也作答不了。"
                  : "活动会按你设的时间推进，但在审核通过前成员看不到、也投不了。")
                : undefined
            }
          />
        )}

        {owesVote && isDeliberation && (
          <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
            <h3 className="section-h">投票</h3>
            <div className="hint" style={{ marginBottom: 8 }}>
              可选 {a.max_choices_per_voter} 项（{a.max_choices_per_voter === 1 ? "一人一票" : "一人多票"}）；一经投出不可更改。
            </div>
            {a.options.map((o) => {
              const on = selected.includes(o.id);
              return (
                <label key={o.id} className={"vote-opt" + (on ? " is-on" : "")}>
                  <input
                    type={a.max_choices_per_voter === 1 ? "radio" : "checkbox"}
                    name="vote-primary"
                    checked={on}
                    onChange={() => toggleOption(o.id)}
                  />
                  <span className="vote-opt-text">{o.text}</span>
                </label>
              );
            })}
            <button className="btn btn-primary btn-sm" onClick={doVote} disabled={busy || selected.length < 1}>投票</button>
          </div>
        )}

        {owesSubmit && (
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

        {memberDebt && canManage && (
          <details className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
            <summary className="section-h" style={{ cursor: "pointer" }}>管理活动</summary>
            <div style={{ marginTop: "var(--s-3)", display: "flex", gap: 8, flexWrap: "wrap" }}>
              {a.status === "scheduled" && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/activity/${a.id}/edit`)}>编辑</button>
              )}
              {(a.status === "open" || a.status === "collecting") && (
                <button className="btn btn-ghost btn-sm" onClick={doClose} disabled={busy}>
                  {closeLabel}
                </button>
              )}
            </div>
          </details>
        )}

        {(a.body || (!memberDebt && canManage && (a.status === "open" || a.status === "collecting"))) && (
        <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
          {a.body && <div className="prose" dangerouslySetInnerHTML={{ __html: a.body }} />}
          {!memberDebt && canManage && (a.status === "open" || a.status === "collecting") && (
            <div style={{ marginTop: "var(--s-4)" }}>
              <button className="btn btn-ghost btn-sm" onClick={doClose} disabled={busy}>
                {closeLabel}
              </button>
            </div>
          )}
        </div>
        )}

        {isSurvey && (
          <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
            <h3 className="section-h">问卷</h3>
            {canEditSchema && (
              <div style={{ marginBottom: 12 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/activity/${a.id}/survey-edit`)}>编辑问卷</button>
              </div>
            )}
            {a.status === "scheduled" && (
              <p className="muted">调研尚未开始。{canEditSchema ? "可先编辑问卷。" : "开始后即可作答。"}</p>
            )}
            {a.status === "open" && !surveyApproved && (
              <p className="muted">审核通过后即可作答。</p>
            )}
            {a.status === "open" && surveyApproved && alreadySubmitted && (
              <p className="muted">你已经提交过了。</p>
            )}
            {a.status === "open" && surveyApproved && guestSubmitted && (
              <div>
                <p>感谢作答。</p>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => { setGuestSubmitted(false); setFillKey((k) => k + 1); }}
                >
                  再填一份
                </button>
              </div>
            )}
            {canFillSurvey && (
              <SurveyFill
                key={fillKey}
                schema={a.schema || { pages: [{ name: "page1", elements: [] }] }}
                onComplete={async (answers) => {
                  const updated = await activityApi.respond(a.id, answers);
                  setActivity(updated);
                  if (!updated.my_response) setGuestSubmitted(true);
                }}
              />
            )}
            {a.status === "closed" && (
              <p className="muted">征答已结束。{a.response_count != null ? `已收到 ${a.response_count} 份作答。` : ""}</p>
            )}
          </div>
        )}

        <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
          <h3 className="section-h">时间线</h3>
          <div className="act-stepper">
            {phases.map((p, i) => (
              <div
                key={p.key}
                className={"act-step" + (i === currentIndex ? " is-current" : "") + (i < currentIndex ? " is-done" : "")}
                style={i === currentIndex ? ({ ["--step-progress" as any]: `${Math.round(currentProgress * 100)}%` }) : undefined}
              >
                <div className="act-step-dot">{i < currentIndex ? "✓" : activityPhase(a.type, p.key as ActivityStatus).emoji}</div>
                <div className="act-step-label">{p.label}</div>
                {p.time && <div className="act-step-time">{p.time}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* 众议：投票 + 结果（展示的投票集成在展品画廊内） */}
        {isDeliberation && !owesVote && (
          <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
            <h3 className="section-h">投票</h3>
            {a.status === "open" && a.my_selections === null && !owesVote ? (
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
                <li>单文件大小上限：{a.max_file_size ? `${Math.round(a.max_file_size / 1024 / 1024)} MB` : `${syncMb} MB`}</li>
                <li>单作品文件数上限：{a.max_files_per_submission}</li>
                <li>最大征集数量：{a.max_submissions ?? "不限"}{a.max_submissions && a.submissions ? `（已收 ${a.submissions.length}）` : ""}</li>
              </ul>
            </div>

            {a.status === "collecting" && !a.my_submission && !owesSubmit && (
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

        {/* 展示：展品画廊——启用投票时每个展品即一个投票选项（1..K）+ 赞/踩；纯陈列仅展品 + 赞/踩 */}
        {isExhibition && (
          (() => {
            const votingActive = a.voting_enabled; // #56：未启用投票=纯陈列，无投票/计票区
            const voted = a.my_selections !== null;
            const mySel = a.my_selections ?? [];
            const canVote = votingActive && a.status === "open" && !voted;
            return (
              <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
                <h3 className="section-h">展品 ({a.exhibits?.length || 0})</h3>
                {canVote && (
                  <div className="hint" style={{ marginBottom: 8 }}>
                    投票：可选 {a.max_choices_per_voter} 个展品（{a.max_choices_per_voter === 1 ? "一人一展品" : "一人多展品"}），一经投出不可更改。赞/踩另算、可随时改。
                  </div>
                )}
                {canManageExhibits && (
                  canVote ? (
                    <details style={{ marginBottom: 12 }}>
                      <summary className="muted" style={{ cursor: "pointer" }}>布展 / 管理</summary>
                      <div className="alert alert-info" style={{ marginTop: 8 }}>
                        <span>{a.status === "scheduled" ? "布展中（待开始）——可加 / 改 / 删展品，或从征集导入；开放后仍可加 / 删，但标题锁定。" : "展示中——可继续加 / 导入 / 删展品；已上架展品的标题已锁定。"}</span>
                        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                          <input className="input" style={{ flex: "1 1 160px" }} value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="新展品标题（选填）" />
                          <input type="file" multiple onChange={(e) => setNewFiles(Array.from(e.target.files || []))} />
                          <button className="btn btn-primary btn-sm" onClick={doAddExhibit} disabled={busy || newFiles.length < 1}>+ 加展品</button>
                          <button className="btn btn-ghost btn-sm" onClick={openImport}>从征集导入</button>
                        </div>
                      </div>
                    </details>
                  ) : (
                  <div className="alert alert-info" style={{ marginBottom: 12 }}>
                    <span>{a.status === "scheduled" ? "布展中（待开始）——可加 / 改 / 删展品，或从征集导入；开放后仍可加 / 删，但标题锁定。" : "展示中——可继续加 / 导入 / 删展品；已上架展品的标题已锁定。"}</span>
                    <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      <input className="input" style={{ flex: "1 1 160px" }} value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="新展品标题（选填）" />
                      <input type="file" multiple onChange={(e) => setNewFiles(Array.from(e.target.files || []))} />
                      <button className="btn btn-primary btn-sm" onClick={doAddExhibit} disabled={busy || newFiles.length < 1}>+ 加展品</button>
                      <button className="btn btn-ghost btn-sm" onClick={openImport}>从征集导入</button>
                    </div>
                  </div>
                  )
                )}
                {importOpen && (
                  <div className="card card-pad" style={{ margin: "12px 0", background: "var(--c-surface-2, #f9fafb)" }}>
                    <h4 className="section-h">从征集导入</h4>
                    {collections.length === 0 ? (
                      <>
                        <p className="muted">暂无可导入的征集（先发起一场征集收件）。</p>
                        <button className="btn btn-ghost btn-sm" onClick={() => setImportOpen(false)}>关闭</button>
                      </>
                    ) : (
                      <>
                        <div className="field">
                          <label className="label">选择征集</label>
                          <select className="input" value={pickedCollection ?? ""} onChange={(e) => pickCollection(Number(e.target.value))}>
                            {collections.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                          </select>
                        </div>
                        {collectionDetail && collectionDetail.submissions && collectionDetail.submissions.length > 0 ? (
                          <>
                            <div className="hint" style={{ marginBottom: 8 }}>勾选要导入的作品（任意状态均可，复制成独立副本）。</div>
                            {collectionDetail.submissions.map((s) => {
                              const on = pickedSubs.includes(s.id);
                              return (
                                <label key={s.id} className={"vote-opt" + (on ? " is-on" : "")} style={{ marginBottom: 6 }}>
                                  <input type="checkbox" checked={on} onChange={() => setPickedSubs((cur) => on ? cur.filter((x) => x !== s.id) : [...cur, s.id])} />
                                  <span className="vote-opt-text">{`@${s.submitter.username}`} · {s.files.length} 个文件</span>
                                </label>
                              );
                            })}
                            <button className="btn btn-primary btn-sm" onClick={doImport} disabled={busy || pickedSubs.length < 1}>导入 {pickedSubs.length} 件</button>
                            <button className="btn btn-ghost btn-sm" onClick={() => setImportOpen(false)}>取消</button>
                          </>
                        ) : (
                          <p className="muted">该征集暂无可见作品。</p>
                        )}
                      </>
                    )}
                  </div>
                )}
                {a.exhibits && a.exhibits.length > 0 ? (
                  <>
                    <div className="exhibit-grid">
                      {a.exhibits.map((ex) => {
                        const oid = ex.vote_option_id;
                        const on = oid != null && selected.includes(oid);
                        const mine = oid != null && mySel.includes(oid);
                        const pct = total > 0 ? Math.round((ex.vote_count / total) * 100) : 0;
                        return (
                          <div key={ex.id} className={"exhibit-card" + (mine ? " is-mine" : "")}>
                            <div className="exhibit-media">{ex.files.map(renderExFile)}</div>
                            <div className="exhibit-title">{ex.title || "未命名"}</div>
                            {canVote ? (
                              <div className="exhibit-vote">
                                <button
                                  type="button"
                                  className={"vote-opt" + (on ? " is-on" : "")}
                                  disabled={busy || (oid == null || (!on && selected.length >= a.max_choices_per_voter))}
                                  onClick={() => oid != null && toggleOption(oid)}
                                >
                                  {on ? "✓ 已选" : "投票"}
                                </button>
                              </div>
                            ) : votingActive ? (
                              <div className="exhibit-tally">
                                <div style={{ display: "flex", justifyContent: "space-between" }}>
                                  <span>{ex.vote_count} 票</span>
                                  <span className="muted">{pct}%</span>
                                </div>
                                <div style={{ height: 6, background: "#e5e7eb", borderRadius: 3, overflow: "hidden", marginTop: 3 }}>
                                  <div style={{ width: `${pct}%`, height: "100%", background: "#2563eb" }} />
                                </div>
                                {mine && <div className="muted" style={{ marginTop: 2 }}>你投了这项</div>}
                              </div>
                            ) : null}
                            <div className="exhibit-rate">
                              <button className={"rate-btn" + (ex.my_rating === "like" ? " is-on like" : "")} onClick={() => doRate(ex.id, "like")} disabled={busy || a.status !== "open"}>👍 {ex.like_count}</button>
                              <button className={"rate-btn" + (ex.my_rating === "dislike" ? " is-on dislike" : "")} onClick={() => doRate(ex.id, "dislike")} disabled={busy || a.status !== "open"}>👎 {ex.dislike_count}</button>
                            </div>
                            {canManageExhibits && (
                              <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
                                {canEditExhibit && <button className="btn btn-ghost btn-sm" onClick={() => doUpdateExhibit(ex.id, ex.title)} disabled={busy}>改</button>}
                                <button className="btn btn-ghost btn-sm" onClick={() => doDeleteExhibit(ex.id)} disabled={busy}>删</button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {canVote && (
                      <div style={{ marginTop: 8 }}>
                        <button className="btn btn-primary btn-sm" onClick={doVote} disabled={busy || selected.length < 1}>投票</button>
                      </div>
                    )}
                    {votingActive && !canVote && <div className="muted" style={{ marginTop: 8 }}>共 {total} 人投票</div>}
                    {votingActive && a.ballots && a.ballots.length > 0 && (
                      <details style={{ marginTop: 12 }}>
                        <summary className="muted">查看投票明细（{a.ballots.length}）</summary>
                        <ul style={{ marginTop: 8 }}>
                          {a.ballots.map((b) => {
                            const names = (a.exhibits || [])
                              .filter((ex) => ex.vote_option_id != null && b.option_ids.includes(ex.vote_option_id))
                              .map((ex) => ex.title || "未命名");
                            return (
                              <li key={b.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0" }}>
                                <Avatar user={b.voter} />
                                <span>{b.voter.nickname || b.voter.username}</span>
                                <span className="muted">投：{names.join("、") || "—"}</span>
                              </li>
                            );
                          })}
                        </ul>
                      </details>
                    )}
                    {votingActive && a.ballots === null && (
                      <div className="alert alert-info" style={{ marginTop: 12 }}>
                        <span>秘密投票 —— 个人投票明细不公开。</span>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="empty-text">暂无展品。</p>
                )}
              </div>
            );
          })()
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
    </PageChrome>
  );
}
