import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import {
  examApi,
  type Exam,
  type ExamBatch,
  type ExamErrata,
  type ExamListItem,
  type ExamWritePayload,
} from "../api/exam";
import { onExamBoardEvent, startExamBoardSocket, stopExamBoardSocket } from "../api/examSocket";
import { useLoginModal } from "../components/LoginModalProvider";
import "../styles/exam-board.css";

const SYNC_INTERVAL = 5 * 60 * 1000;
const SELECTION_KEY = "examBoardSelection";
const SHANGHAI = "Asia/Shanghai";

type DraftSubject = {
  key: string;
  name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
};
type DraftBatch = { key: string; name: string; subjects: DraftSubject[] };

type BoardStatus =
  | { kind: "empty" }
  | { kind: "idle" }
  | { kind: "active"; subject: string; start: string; end: string }
  | { kind: "rest"; nextSubject: string; nextStart: string }
  | { kind: "done" };

function shanghaiParts(ms: number) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: SHANGHAI,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(ms));
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? "00";
  return {
    date: `${get("year")}-${get("month")}-${get("day")}`,
    time: `${get("hour")}:${get("minute")}:${get("second")}`,
    hm: `${get("hour")}:${get("minute")}`,
  };
}

function hm(value: string) {
  return (value || "").slice(0, 5);
}

function newKey() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadSelection(): { examId: number | null; batchId: number | null } {
  try {
    const raw = localStorage.getItem(SELECTION_KEY);
    if (!raw) return { examId: null, batchId: null };
    const parsed = JSON.parse(raw);
    return {
      examId: typeof parsed.examId === "number" ? parsed.examId : null,
      batchId: typeof parsed.batchId === "number" ? parsed.batchId : null,
    };
  } catch {
    return { examId: null, batchId: null };
  }
}

function examToDraft(exam: Exam): { title: string; batches: DraftBatch[] } {
  return {
    title: exam.title,
    batches: exam.batches.map((b) => ({
      key: `b-${b.id}`,
      name: b.name,
      subjects: b.subjects.map((s) => ({
        key: `s-${s.id}`,
        name: s.name,
        exam_date: s.exam_date,
        start_time: hm(s.start_time),
        end_time: hm(s.end_time),
      })),
    })),
  };
}

function emptyDraft() {
  return {
    title: "",
    batches: [
      {
        key: newKey(),
        name: "高一",
        subjects: [
          { key: newKey(), name: "语文", exam_date: "", start_time: "09:00", end_time: "11:30" },
        ],
      },
    ],
  };
}

function draftToPayload(title: string, batches: DraftBatch[]): ExamWritePayload {
  return {
    title: title.trim(),
    batches: batches.map((b, i) => ({
      name: b.name.trim(),
      sort_order: i,
      subjects: b.subjects
        .filter((s) => s.name.trim() && s.exam_date && s.start_time && s.end_time)
        .map((s, j) => ({
          name: s.name.trim(),
          exam_date: s.exam_date,
          start_time: s.start_time,
          end_time: s.end_time,
          sort_order: j,
        })),
    })),
  };
}

function matchBoard(subjects: ExamBatch["subjects"], nowMs: number): BoardStatus {
  if (!subjects.length) return { kind: "empty" };
  const { date, hm: nowHm } = shanghaiParts(nowMs);
  const today = subjects
    .filter((s) => s.exam_date === date)
    .slice()
    .sort((a, b) => hm(a.start_time).localeCompare(hm(b.start_time)));
  if (!today.length) return { kind: "idle" };
  for (const s of today) {
    const start = hm(s.start_time);
    const end = hm(s.end_time);
    if (nowHm >= start && nowHm < end) {
      return { kind: "active", subject: s.name, start, end };
    }
  }
  const next = today.find((s) => hm(s.start_time) > nowHm);
  if (next) return { kind: "rest", nextSubject: next.name, nextStart: hm(next.start_time) };
  return { kind: "done" };
}

export default function ExamBoardPage() {
  const { openLogin, authNonce } = useLoginModal();
  const [canManage, setCanManage] = useState(false);
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [exam, setExam] = useState<Exam | null>(null);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [tab, setTab] = useState<"display" | "edit" | "errata">("display");
  const [currentTime, setCurrentTime] = useState("00:00:00");
  const [status, setStatus] = useState<BoardStatus>({ kind: "idle" });
  const [errata, setErrata] = useState<ExamErrata | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBatches, setDraftBatches] = useState<DraftBatch[]>(emptyDraft().batches);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const [errataText, setErrataText] = useState("");
  const [errataFile, setErrataFile] = useState<File | null>(null);
  const timeOffsetRef = useRef(0);

  const batch = useMemo(
    () => exam?.batches.find((b) => b.id === batchId) ?? exam?.batches[0] ?? null,
    [exam, batchId],
  );

  const persistSelection = (examId: number | null, nextBatchId: number | null) => {
    localStorage.setItem(SELECTION_KEY, JSON.stringify({ examId, batchId: nextBatchId }));
  };

  const applyExam = useCallback((next: Exam | null, preferredBatchId?: number | null) => {
    setExam(next);
    if (!next) {
      setBatchId(null);
      return;
    }
    const preferred = preferredBatchId ?? loadSelection().batchId;
    const found = next.batches.find((b) => b.id === preferred);
    const chosen = found?.id ?? next.batches[0]?.id ?? null;
    setBatchId(chosen);
    persistSelection(next.id, chosen);
  }, []);

  const loadExam = useCallback(async (id: number, preferredBatchId?: number | null) => {
    const next = await examApi.retrieve(id);
    applyExam(next, preferredBatchId);
  }, [applyExam]);

  const refresh = useCallback(async () => {
    const [list, current] = await Promise.all([
      examApi.list(),
      examApi.currentErrata().catch(() => ({ data: null })),
    ]);
    setExams(list.results);
    setErrata(current.data);
    const saved = loadSelection();
    const fallbackId = list.results[0]?.id ?? null;
    const targetId = list.results.some((e) => e.id === saved.examId) ? saved.examId : fallbackId;
    if (targetId == null) {
      applyExam(null);
      return;
    }
    await loadExam(targetId, saved.examId === targetId ? saved.batchId : null);
  }, [applyExam, loadExam]);

  const syncTime = useCallback(async () => {
    try {
      const data = await examApi.clock();
      timeOffsetRef.current = data.timestamp - Date.now();
    } catch {
      timeOffsetRef.current = 0;
    }
  }, []);

  useEffect(() => {
    api.me()
      .then((d) => setCanManage(!!d.user?.permissions?.can_manage_exam))
      .catch(() => setCanManage(false));
  }, [authNonce]);

  useEffect(() => {
    document.title = "考试看板";
    refresh().catch(() => {});
    startExamBoardSocket();
    const stop = onExamBoardEvent((ev) => {
      if (ev.event === "exam") refresh().catch(() => {});
      if (ev.event === "errata") {
        examApi.currentErrata().then((r) => setErrata(r.data)).catch(() => {});
      }
      if (ev.event === "errata_cleared") setErrata(null);
    });
    return () => {
      stop();
      stopExamBoardSocket();
    };
  }, [refresh]);

  useEffect(() => {
    syncTime();
    const t = setInterval(syncTime, SYNC_INTERVAL);
    return () => clearInterval(t);
  }, [syncTime]);

  useEffect(() => {
    const tick = () => {
      const nowMs = Date.now() + timeOffsetRef.current;
      const { time } = shanghaiParts(nowMs);
      setCurrentTime(time);
      setStatus(matchBoard(batch?.subjects ?? [], nowMs));
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [batch]);

  const openSettings = () => {
    setTab("display");
    setSaveError("");
    if (exam) {
      const d = examToDraft(exam);
      setEditingId(exam.id);
      setDraftTitle(d.title);
      setDraftBatches(d.batches);
    } else {
      setEditingId(null);
      const d = emptyDraft();
      setDraftTitle(d.title);
      setDraftBatches(d.batches);
    }
    setIsModalOpen(true);
  };

  const startNewExam = () => {
    const d = emptyDraft();
    setEditingId(null);
    setDraftTitle(d.title);
    setDraftBatches(d.batches);
    setTab("edit");
  };

  const loadForEdit = async (id: number) => {
    const next = await examApi.retrieve(id);
    const d = examToDraft(next);
    setEditingId(next.id);
    setDraftTitle(d.title);
    setDraftBatches(d.batches);
    setTab("edit");
  };

  const handleSaveExam = async () => {
    setSaving(true);
    setSaveError("");
    try {
      const payload = draftToPayload(draftTitle, draftBatches);
      const saved = editingId
        ? await examApi.update(editingId, payload)
        : await examApi.create(payload);
      await refresh();
      applyExam(saved, saved.batches[0]?.id ?? null);
      setIsModalOpen(false);
    } catch (e: any) {
      if (e?.apiError?.kind === "auth") {
        setIsModalOpen(false);
        openLogin();
        return;
      }
      setSaveError(e?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handlePublishErrata = async () => {
    setSaving(true);
    setSaveError("");
    try {
      const data = new FormData();
      data.append("text", errataText);
      if (errataFile) data.append("image", errataFile);
      const published = await examApi.publishErrata(data);
      setErrata(published);
      setErrataText("");
      setErrataFile(null);
      setIsModalOpen(false);
    } catch (e: any) {
      if (e?.apiError?.kind === "auth") {
        setIsModalOpen(false);
        openLogin();
        return;
      }
      setSaveError(e?.message || "发布失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDismissErrata = async () => {
    setSaving(true);
    try {
      await examApi.dismissErrata();
      setErrata(null);
    } catch (e: any) {
      setSaveError(e?.message || "撤回失败");
    } finally {
      setSaving(false);
    }
  };

  const subjectLabel =
    status.kind === "active" ? status.subject
    : status.kind === "rest" ? "休息"
    : status.kind === "done" ? "已结束"
    : status.kind === "empty" ? "无"
    : "无";
  const startLabel = status.kind === "active" ? status.start : status.kind === "rest" ? status.nextStart : "--:--";
  const endLabel = status.kind === "active" ? status.end : "--:--";
  const startCaption = status.kind === "rest" ? "下场开始：" : "开始时间：";

  return (
    <div className="exam-board-wrapper">
      <button id="settings-btn" className="settings-btn" title="设置" onClick={openSettings}>
        ⚙️
      </button>

      {isModalOpen && (
        <div className="modal" onClick={() => setIsModalOpen(false)}>
          <div className="modal-content exam-settings" onClick={(e) => e.stopPropagation()}>
            <span className="close-btn" onClick={() => setIsModalOpen(false)}>&times;</span>
            <h3>考试看板设置</h3>
            <div className="settings-tabs">
              <button type="button" className={tab === "display" ? "active" : ""} onClick={() => setTab("display")}>显示批次</button>
              {canManage && (
                <>
                  <button type="button" className={tab === "edit" ? "active" : ""} onClick={() => setTab("edit")}>编辑考试</button>
                  <button type="button" className={tab === "errata" ? "active" : ""} onClick={() => setTab("errata")}>题目误刊</button>
                </>
              )}
            </div>

            {tab === "display" && (
              <div className="settings-body">
                <label>
                  考试
                  <select
                    value={exam?.id ?? ""}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      if (!id) return;
                      loadExam(id).catch(() => {});
                    }}
                  >
                    {exams.length === 0 && <option value="">暂无考试</option>}
                    {exams.map((item) => (
                      <option key={item.id} value={item.id}>{item.title}</option>
                    ))}
                  </select>
                </label>
                <label>
                  批次
                  <select
                    value={batch?.id ?? ""}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      setBatchId(id);
                      if (exam) persistSelection(exam.id, id);
                    }}
                  >
                    {(exam?.batches ?? []).map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </label>
                {batch && (
                  <ul className="subject-preview">
                    {batch.subjects.map((s) => (
                      <li key={s.id}>{s.exam_date} {s.name} {hm(s.start_time)}–{hm(s.end_time)}</li>
                    ))}
                    {batch.subjects.length === 0 && <li>该批次暂无科目</li>}
                  </ul>
                )}
              </div>
            )}

            {tab === "edit" && canManage && (
              <div className="settings-body">
                <div className="edit-toolbar">
                  <select
                    value={editingId ?? ""}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      if (id) loadForEdit(id).catch(() => {});
                    }}
                  >
                    <option value="">新建考试</option>
                    {exams.map((item) => (
                      <option key={item.id} value={item.id}>{item.title}</option>
                    ))}
                  </select>
                  <button type="button" className="btn-add" onClick={startNewExam}>+ 新建</button>
                </div>
                <label>
                  考试标题
                  <input value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} placeholder="如 2026 学年期末考试" />
                </label>
                {draftBatches.map((b, bi) => (
                  <div className="batch-editor" key={b.key}>
                    <div className="batch-head">
                      <input
                        value={b.name}
                        onChange={(e) => setDraftBatches(draftBatches.map((x, i) => i === bi ? { ...x, name: e.target.value } : x))}
                        placeholder="批次名称，如 高一"
                      />
                      <button type="button" className="btn-delete" onClick={() => setDraftBatches(draftBatches.filter((_, i) => i !== bi))}>删除批次</button>
                    </div>
                    <table className="schedule-table">
                      <thead>
                        <tr>
                          <th>日期</th>
                          <th>科目</th>
                          <th>开始</th>
                          <th>结束</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {b.subjects.map((s, si) => (
                          <tr key={s.key}>
                            <td>
                              <input
                                type="date"
                                value={s.exam_date}
                                onChange={(e) => setDraftBatches(draftBatches.map((x, i) => i === bi ? {
                                  ...x,
                                  subjects: x.subjects.map((y, j) => j === si ? { ...y, exam_date: e.target.value } : y),
                                } : x))}
                              />
                            </td>
                            <td>
                              <input
                                value={s.name}
                                onChange={(e) => setDraftBatches(draftBatches.map((x, i) => i === bi ? {
                                  ...x,
                                  subjects: x.subjects.map((y, j) => j === si ? { ...y, name: e.target.value } : y),
                                } : x))}
                              />
                            </td>
                            <td>
                              <input
                                type="time"
                                value={s.start_time}
                                onChange={(e) => setDraftBatches(draftBatches.map((x, i) => i === bi ? {
                                  ...x,
                                  subjects: x.subjects.map((y, j) => j === si ? { ...y, start_time: e.target.value } : y),
                                } : x))}
                              />
                            </td>
                            <td>
                              <input
                                type="time"
                                value={s.end_time}
                                onChange={(e) => setDraftBatches(draftBatches.map((x, i) => i === bi ? {
                                  ...x,
                                  subjects: x.subjects.map((y, j) => j === si ? { ...y, end_time: e.target.value } : y),
                                } : x))}
                              />
                            </td>
                            <td>
                              <button
                                type="button"
                                className="btn-delete"
                                onClick={() => setDraftBatches(draftBatches.map((x, i) => i === bi ? {
                                  ...x,
                                  subjects: x.subjects.filter((_, j) => j !== si),
                                } : x))}
                              >
                                删
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <button
                      type="button"
                      className="btn-add"
                      onClick={() => setDraftBatches(draftBatches.map((x, i) => i === bi ? {
                        ...x,
                        subjects: [...x.subjects, { key: newKey(), name: "", exam_date: "", start_time: "09:00", end_time: "11:00" }],
                      } : x))}
                    >
                      + 添加科目
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn-add"
                  onClick={() => setDraftBatches([...draftBatches, { key: newKey(), name: "", subjects: [] }])}
                >
                  + 添加批次
                </button>
                {saveError && <p className="settings-error">{saveError}</p>}
                <div className="modal-actions">
                  <button type="button" className="btn-save" disabled={saving} onClick={handleSaveExam}>
                    {saving ? "保存中…" : "保存到服务器"}
                  </button>
                </div>
              </div>
            )}

            {tab === "errata" && canManage && (
              <div className="settings-body">
                <p className="settings-hint">发布后所有打开的考试看板会立刻弹出图文更正。</p>
                <label>
                  说明
                  <textarea value={errataText} onChange={(e) => setErrataText(e.target.value)} rows={3} placeholder="如：语文第 3 题更正为……" />
                </label>
                <label>
                  图片
                  <input type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={(e) => setErrataFile(e.target.files?.[0] ?? null)} />
                </label>
                {saveError && <p className="settings-error">{saveError}</p>}
                <div className="modal-actions">
                  {errata && (
                    <button type="button" className="btn-delete" disabled={saving} onClick={handleDismissErrata}>撤回当前</button>
                  )}
                  <button type="button" className="btn-save" disabled={saving} onClick={handlePublishErrata}>广播误刊</button>
                </div>
              </div>
            )}

            {!canManage && tab !== "display" && (
              <p className="settings-hint">登录且持有「管理考试看板」后可编辑课表、广播误刊。</p>
            )}
          </div>
        </div>
      )}

      {errata && (
        <div className="errata-overlay" role="alert">
          <div className="errata-card">
            <div className="errata-kicker">题目误刊</div>
            {errata.image_url && <img src={errata.image_url} alt="" />}
            {errata.text && <p>{errata.text}</p>}
          </div>
        </div>
      )}

      <div className="board-container">
        <div className="exam-heading">
          <span id="exam-title">{exam?.title || "暂无考试"}</span>
          {batch && <span id="exam-batch">{batch.name}</span>}
        </div>
        <div className="row1">
          <span id="current-time">{currentTime}</span>
        </div>
        <div className="info-grid">
          <div className="left-col">
            <span>当前科目：</span>
            <span id="current-subject">{subjectLabel}</span>
          </div>
          <div className="right-col" id="start-time-container">
            <span>{startCaption}</span>
            <span id="start-time">{startLabel}</span>
          </div>
        </div>
        <div className="info-grid">
          <div className="empty-col">
            {status.kind === "rest" && <span className="rest-hint">下场：{status.nextSubject}</span>}
          </div>
          <div className="right-col" id="end-time-container">
            <span>结束时间：</span>
            <span id="end-time">{endLabel}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
