import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { proposalApi } from "../api/proposals";
import {
  ActivityType,
  ActivityFormData,
  ProposalDetail,
  ACTIVITY_TYPE_LABELS,
} from "../types/proposals";
import RichTextEditor from "../components/RichTextEditor";
import AppShell from "../components/AppShell";
import "../styles/form.css";

export default function ProposalFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = !!id;

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [activityType, setActivityType] = useState<ActivityType | "">("");
  const [plannedDate, setPlannedDate] = useState("");
  const [location, setLocation] = useState("");
  const [expectedParticipants, setExpectedParticipants] = useState("");
  const [budget, setBudget] = useState("");

  useEffect(() => {
    if (!isEdit) return;
    setLoading(true);
    proposalApi.get(Number(id))
      .then((p: ProposalDetail) => {
        // 仅「已打回」状态可编辑
        if (p.status !== "returned" || p.proposal_type !== "activity") {
          setBlocked(true);
          return;
        }
        setTitle(p.title);
        setDescription(p.description);
        setActivityType(p.activity_type);
        setPlannedDate(p.planned_date || "");
        setLocation(p.location);
        setExpectedParticipants(p.expected_participants != null ? String(p.expected_participants) : "");
        setBudget(p.budget != null ? String(p.budget) : "");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("标题不能为空");
      return;
    }
    setSaving(true);
    setError("");

    const data: ActivityFormData = {
      proposal_type: "activity",
      title: title.trim(),
      description,
      activity_type: activityType,
    };
    if (plannedDate) data.planned_date = plannedDate;
    if (location.trim()) data.location = location.trim();
    if (expectedParticipants) data.expected_participants = Number(expectedParticipants);
    if (budget) data.budget = Number(budget);

    try {
      const result = isEdit
        ? await proposalApi.update(Number(id), data)
        : await proposalApi.createActivity(data);
      navigate(`/activity/${result.id}`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="container" style={{ paddingTop: "var(--s-12)" }}>
          <p className="muted">加载中…</p>
        </div>
      </AppShell>
    );
  }

  if (blocked) {
    return (
      <AppShell>
        <div className="container" style={{ paddingTop: "var(--s-12)", paddingBottom: "var(--s-16)" }}>
          <div className="form-card">
            <div className="card card-pad">
              <div className="alert alert-warning" style={{ marginBottom: "var(--s-4)" }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4M12 17h.01" /></svg>
                <span>该申报当前状态不可编辑（仅「已打回」的活动申报可修改）。</span>
              </div>
              <button className="btn btn-primary" onClick={() => navigate(`/activity/${id}`)}>返回详情</button>
            </div>
          </div>
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
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动申报</a>
            <span className="sep">/</span>
            <span>{isEdit ? "编辑" : "新建"}</span>
          </nav>
          <div className="page-head-row">
            <h1>{isEdit ? "修改活动申报" : "新建活动申报"}</h1>
          </div>
        </div>
      </div>

      <div className="container" style={{ paddingTop: "var(--s-12)", paddingBottom: "var(--s-16)" }}>
        <div className="form-card">
          {error && (
            <div className="alert alert-danger" style={{ marginBottom: "var(--s-4)" }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="card card-pad form-stack">
            <div className="field">
              <label className="label">标题 <span className="hint">*</span></label>
              <input className="input" type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="活动名称" maxLength={200} required />
            </div>

            <div className="field">
              <label className="label">详细说明</label>
              <RichTextEditor content={description} onChange={setDescription} placeholder="活动背景、目的、流程、预期效果..." />
            </div>

            <div className="form-grid">
              <div className="field">
                <label className="label">活动类型</label>
                <select className="select" value={activityType} onChange={(e) => setActivityType(e.target.value as ActivityType | "")}>
                  <option value="">请选择</option>
                  {(Object.keys(ACTIVITY_TYPE_LABELS) as ActivityType[]).map((k) => (
                    <option key={k} value={k}>{ACTIVITY_TYPE_LABELS[k]}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="label">拟办日期</label>
                <input className="input" type="date" value={plannedDate} onChange={(e) => setPlannedDate(e.target.value)} />
              </div>
            </div>

            <div className="form-grid">
              <div className="field">
                <label className="label">地点</label>
                <input className="input" type="text" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="活动地点" maxLength={200} />
              </div>
              <div className="field">
                <label className="label">预计参与人数</label>
                <input className="input" type="number" min={0} value={expectedParticipants} onChange={(e) => setExpectedParticipants(e.target.value)} placeholder="如 30" />
              </div>
            </div>

            <div className="field">
              <label className="label">预算（元）</label>
              <input className="input" type="number" min={0} step="0.01" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="预计花费" />
            </div>

            {!isEdit && (
              <div className="form-notice">提交后将进入为期 3 天的投票阶段，到期自动进入待社长审批。</div>
            )}

            <div className="form-actions">
              <button type="button" className="btn btn-ghost" onClick={() => navigate(id ? `/activity/${id}` : "/activity")}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? "保存中…" : isEdit ? "保存修改" : "提交并开始投票"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </AppShell>
  );
}
