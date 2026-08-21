import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import { api } from "../api/client";
import { examApi, type ExamItem } from "../api/exam";
import "../styles/detail.css";
import "../styles/form.css";
import "../styles/list.css";

export default function ExamBoardPage() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<ExamItem[]>([]);
  const [canWrite, setCanWrite] = useState(false);
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState("");
  const [title, setTitle] = useState("");
  const [list, setList] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = () => examApi.list().then((d) => setExams(d.results || []));

  useEffect(() => {
    document.title = "考试看板 · 南汇一中传媒社";
    load().catch(() => setExams([]));
    api.me()
      .then((d: any) => setCanWrite(!!d.user?.permissions?.can_manage_exam))
      .catch(() => setCanWrite(false));
  }, []);

  const latest = exams[0];

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await examApi.create({ exam_date: date, exam_title: title.trim(), exam_list: list.trim() });
      setEditing(false);
      setDate(""); setTitle(""); setList("");
      await load();
    } catch (e: any) {
      setError(e?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>考试看板</span>
          </nav>
          <div className="page-head-row">
            <div>
              <h1>考试看板</h1>
              <p className="section-sub">最近一场考试安排（日期 / 标题 / 科目）。</p>
            </div>
            {canWrite && !editing && (
              <button className="btn btn-primary" onClick={() => setEditing(true)}>写入考试</button>
            )}
          </div>
        </div>
      </div>
      <div className="container detail-container">
        {latest ? (
          <div className="card card-pad">
            <p className="detail-sub">{latest.exam_date}</p>
            <h2 className="detail-title">{latest.exam_title}</h2>
            <p>{latest.exam_list}</p>
          </div>
        ) : (
          <p className="empty-text">暂无考试安排。</p>
        )}

        {editing && (
          <div className="card card-pad form-card" style={{ marginTop: "var(--s-6)" }}>
            <div className="form-stack">
              <label className="field"><span className="label">日期</span>
                <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </label>
              <label className="field"><span className="label">标题</span>
                <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={50} />
              </label>
              <label className="field"><span className="label">科目列表</span>
                <input className="input" value={list} onChange={(e) => setList(e.target.value)} placeholder="语文,数学,英语" maxLength={255} />
              </label>
              {error && <div className="alert alert-danger">{error}</div>}
              <div className="form-actions">
                <button className="btn btn-ghost" onClick={() => setEditing(false)}>取消</button>
                <button className="btn btn-primary" disabled={saving || !date || !title.trim() || !list.trim()} onClick={save}>
                  {saving ? "保存中…" : "保存"}
                </button>
              </div>
            </div>
          </div>
        )}

        {exams.length > 1 && (
          <div style={{ marginTop: "var(--s-8)" }}>
            <h3 className="section-h">历史场次</h3>
            {exams.slice(1).map((e) => (
              <div key={e.id} className="task-card" style={{ cursor: "default" }}>
                <div className="tc-info">
                  <div className="tc-title">{e.exam_title}</div>
                  <div className="tc-meta"><span>{e.exam_date}</span><span>{e.exam_list}</span></div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
