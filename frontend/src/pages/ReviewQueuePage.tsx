import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import { api } from "../api/client";
import { identityReviewsApi } from "../api/identityReviews";
import { reviewsApi } from "../api/reviews";
import ReviewPreview from "./review/ReviewPreview";
import {
  IDENTITY_LABELS,
  IDENTITY_STATUS_BADGE,
  IDENTITY_STATUS_LABELS,
  type IdentityReviewItem,
  type IdentityReviewStatus,
} from "../types/identityReviews";
import {
  type ReviewItem,
  type ReviewStatus,
  type ReviewTargetType,
  TARGET_TYPE_LABELS,
} from "../types/reviews";
import "../styles/list.css";
import "../styles/form.css";
import "../styles/detail.css";

type DeskKind = "identity" | ReviewTargetType;

const ADVANCE_MS = 900;
const CONTENT_KINDS: ReviewTargetType[] = ["news", "activity", "tutorial"];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function firstIdentity(
  status: IdentityReviewStatus,
  excludeId?: number,
): Promise<IdentityReviewItem | null> {
  let page = 1;
  for (;;) {
    const data = await identityReviewsApi.list({ status, page: String(page) });
    const hit = (data.results || []).find((row) => row.id !== excludeId);
    if (hit) return hit;
    if (!data.next) return null;
    page += 1;
  }
}

async function firstContent(
  type: ReviewTargetType,
  status: ReviewStatus | "",
  excludeId?: number,
): Promise<ReviewItem | null> {
  let page = 1;
  for (;;) {
    const params: Record<string, string> = {
      ordering: "created_at",
      page: String(page),
    };
    if (status) params.status = status;
    const data = await reviewsApi.list(params);
    const hit = (data.results || []).find(
      (row) => row.target_type === type && row.id !== excludeId,
    );
    if (hit) return hit;
    if (!data.next) return null;
    page += 1;
  }
}

export default function ReviewQueuePage() {
  const navigate = useNavigate();
  const gen = useRef(0);

  const [canContent, setCanContent] = useState(false);
  const [canIdentity, setCanIdentity] = useState(false);
  const [denied, setDenied] = useState(false);
  const [booting, setBooting] = useState(true);

  const [kind, setKind] = useState<DeskKind | null>(null);
  const [identityStatus, setIdentityStatus] = useState<IdentityReviewStatus>("pending");
  const [contentStatus, setContentStatus] = useState<ReviewStatus | "">("pending");

  const [identityItem, setIdentityItem] = useState<IdentityReviewItem | null>(null);
  const [contentRow, setContentRow] = useState<ReviewItem | null>(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lightboxUrl, setLightboxUrl] = useState("");
  const [flash, setFlash] = useState("");

  const loadPane = useCallback(async (
    nextKind: DeskKind,
    idStatus: IdentityReviewStatus,
    cStatus: ReviewStatus | "",
    excludeId?: number,
    token?: number,
  ) => {
    setLoading(true);
    setError("");
    setLightboxUrl("");
    try {
      if (nextKind === "identity") {
        const item = await firstIdentity(idStatus, excludeId);
        if (token != null && token !== gen.current) return;
        setIdentityItem(item);
        setContentRow(null);
      } else {
        const row = await firstContent(nextKind, cStatus, excludeId);
        if (token != null && token !== gen.current) return;
        setIdentityItem(null);
        setContentRow(row);
      }
    } catch (e: any) {
      if (token != null && token !== gen.current) return;
      setError(e.message || "加载失败");
      setIdentityItem(null);
      setContentRow(null);
    } finally {
      if (token == null || token === gen.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.me()
      .then(async (d: any) => {
        const content = !!d.user?.permissions?.can_review_content;
        const identity = !!d.user?.permissions?.can_review_identity;
        if (cancelled) return;
        setCanContent(content);
        setCanIdentity(identity);
        if (!content && !identity) {
          setDenied(true);
          setBooting(false);
          return;
        }
        const order: DeskKind[] = [];
        if (identity) order.push("identity");
        if (content) order.push(...CONTENT_KINDS);
        const probes = await Promise.all(order.map(async (k) => {
          try {
            if (k === "identity") return { k, hit: await firstIdentity("pending") };
            return { k, hit: await firstContent(k, "pending") };
          } catch {
            return { k, hit: null };
          }
        }));
        if (cancelled) return;
        setKind(probes.find((p) => p.hit)?.k ?? order[0]);
        setBooting(false);
      })
      .catch(() => {
        if (!cancelled) {
          setDenied(true);
          setBooting(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (booting || !kind) return;
    const token = ++gen.current;
    setFlash("");
    loadPane(kind, identityStatus, contentStatus, undefined, token);
  }, [booting, kind, identityStatus, contentStatus, loadPane]);

  useEffect(() => {
    if (!lightboxUrl) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxUrl("");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightboxUrl]);

  const pickKind = (next: DeskKind) => {
    setKind(next);
    setIdentityStatus("pending");
    setContentStatus("pending");
    setFlash("");
  };

  const afterAction = async (excludeId: number, notice: string) => {
    setFlash(notice);
    const token = ++gen.current;
    await sleep(ADVANCE_MS);
    if (token !== gen.current || !kind) return;
    setFlash("");
    await loadPane(kind, identityStatus, contentStatus, excludeId, token);
  };

  const runIdentity = async (
    fn: () => Promise<IdentityReviewItem>,
    notice: string,
    confirmMsg?: string,
  ) => {
    if (!identityItem) return;
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setBusy(true);
    setError("");
    try {
      const updated = await fn();
      setIdentityItem(updated);
      await afterAction(updated.id, notice);
    } catch (e: any) {
      setError(e.message || "操作失败");
    } finally {
      setBusy(false);
    }
  };

  const empty = kind === "identity" ? !identityItem : !contentRow;
  const identityLabel = identityItem
    ? (IDENTITY_LABELS[identityItem.identity] || identityItem.identity || "未填写")
    : "";

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>审核队列</span>
          </nav>
          <div className="page-head-row">
            <div>
              <h1>审核台</h1>
              <p className="section-sub">身份证明与新闻 / 活动 / 教程逐条审核，处理后自动进入下一条。</p>
            </div>
          </div>
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        {denied ? (
          <p className="task-empty">你没有审核权限。</p>
        ) : booting ? (
          <p className="task-empty">加载中…</p>
        ) : (
          <>
            <div className="filter-bar" role="tablist" aria-label="审核类型">
              {canIdentity && (
                <button className="chip" aria-pressed={kind === "identity"}
                        onClick={() => pickKind("identity")}>身份</button>
              )}
              {canContent && CONTENT_KINDS.map((k) => (
                <button key={k} className="chip" aria-pressed={kind === k}
                        onClick={() => pickKind(k)}>{TARGET_TYPE_LABELS[k]}</button>
              ))}
            </div>

            {kind === "identity" ? (
              <div className="filter-bar" role="tablist" aria-label="身份审核状态">
                {(["pending", "approved", "rejected"] as IdentityReviewStatus[]).map((s) => (
                  <button key={s} className="chip" aria-pressed={identityStatus === s}
                          onClick={() => setIdentityStatus(s)}>
                    {IDENTITY_STATUS_LABELS[s]}
                  </button>
                ))}
              </div>
            ) : (
              <div className="filter-bar" role="tablist" aria-label="内容审核状态">
                <button className="chip" aria-pressed={contentStatus === "pending"}
                        onClick={() => setContentStatus("pending")}>待审</button>
                <button className="chip" aria-pressed={contentStatus === "approved"}
                        onClick={() => setContentStatus("approved")}>已通过</button>
                <button className="chip" aria-pressed={contentStatus === "rejected"}
                        onClick={() => setContentStatus("rejected")}>已驳回</button>
                <button className="chip" aria-pressed={contentStatus === "removed"}
                        onClick={() => setContentStatus("removed")}>已下架</button>
                <button className="chip" aria-pressed={contentStatus === ""}
                        onClick={() => setContentStatus("")}>全部</button>
              </div>
            )}

            {error && <div className="alert alert-warning" style={{ marginBottom: 12 }}>{error}</div>}

            {loading ? (
              <p className="task-empty">加载中…</p>
            ) : empty ? (
              <p className="task-empty">本队列已空</p>
            ) : kind === "identity" && identityItem ? (
              <div className="desk-pane">
                <div className="desk-meta">
                  <span className={"badge " + IDENTITY_STATUS_BADGE[identityItem.status]}>
                    {IDENTITY_STATUS_LABELS[identityItem.status]}
                  </span>
                  {flash && <span className="badge badge-brand">{flash}</span>}
                </div>
                <h2 className="desk-title">{identityItem.real_name || identityItem.username}</h2>
                <div className="desk-sub">
                  <span>用户名 {identityItem.username}</span>
                  <span className="sep">·</span>
                  <span>{identityLabel}</span>
                  {identityItem.verified_by && (
                    <>
                      <span className="sep">·</span>
                      <span>审核人 @{identityItem.verified_by.username}</span>
                    </>
                  )}
                </div>
                {identityItem.proofs.length === 0 ? (
                  <p className="empty-text">没有证明材料。</p>
                ) : (
                  <div className="desk-proofs">
                    {identityItem.proofs.map((p) => (
                      <button key={p.id} type="button" className="desk-proof"
                              onClick={() => setLightboxUrl(p.url)}
                              aria-label="查看完整证明图">
                        <img src={p.url} alt="身份证明" />
                      </button>
                    ))}
                  </div>
                )}
                <div className="desk-actions">
                  {identityItem.status === "pending" && (
                    <>
                      <button className="btn btn-primary" disabled={busy}
                              onClick={() => runIdentity(
                                () => identityReviewsApi.approve(identityItem.id),
                                "已通过",
                              )}>通过</button>
                      <button className="btn btn-ghost" disabled={busy}
                              onClick={() => runIdentity(
                                () => identityReviewsApi.reject(identityItem.id),
                                "已驳回",
                              )}>驳回</button>
                    </>
                  )}
                  <button className="btn btn-danger" disabled={busy}
                          onClick={() => runIdentity(
                            () => identityReviewsApi.disable(identityItem.id),
                            "账号已停用",
                            "确定停用该账号？对方将立即无法登录。",
                          )}>停用账号</button>
                </div>
              </div>
            ) : contentRow ? (
              <ReviewPreview
                key={`${contentRow.target_type}-${contentRow.target_id}`}
                review={contentRow}
                flash={flash}
                onModerated={async (updated, notice) => {
                  setContentRow(updated);
                  await afterAction(updated.id, notice);
                }}
              />
            ) : null}
          </>
        )}
      </div>

      {lightboxUrl && (
        <div className="desk-lightbox" role="dialog" aria-label="身份证明大图"
             onClick={() => setLightboxUrl("")}>
          <img src={lightboxUrl} alt="身份证明" onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </AppShell>
  );
}
