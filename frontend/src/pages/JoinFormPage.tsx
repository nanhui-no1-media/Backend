import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Model } from "survey-core";
import { Survey } from "survey-react-ui";
import "survey-core/survey-core.css";
import AppShell from "../components/AppShell";
import { recruitmentApi } from "../api/recruitment";
import "../styles/detail.css";

export default function JoinFormPage() {
  const navigate = useNavigate();
  const [schema, setSchema] = useState<Record<string, unknown> | null>(null);
  const [done, setDone] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "自我介绍问卷";
    if (sessionStorage.getItem("join_notice_ack") !== "1") {
      navigate("/join", { replace: true });
      return;
    }
    recruitmentApi.landing().then((d) => setSchema(d.schema));
  }, [navigate]);

  const model = useMemo(() => {
    if (!schema) return null;
    const m = new Model(schema);
    m.onComplete.add(async (sender) => {
      try {
        const res = await recruitmentApi.submit(sender.data, true);
        sessionStorage.removeItem("join_notice_ack");
        setDone(res.message || "报名已提交");
      } catch (e: any) {
        setError(e?.message || "提交失败");
      }
    });
    return m;
  }, [schema]);

  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/join"); }}>加入社团</a>
            <span className="sep">/</span>
            <span>自我介绍问卷</span>
          </nav>
          <h1>自我介绍问卷</h1>
        </div>
      </div>
      <div className="container detail-container">
        {error && <div className="alert alert-danger">{error}</div>}
        {done ? (
          <div className="card card-pad"><p>{done}</p>
            <button className="btn btn-primary" onClick={() => navigate("/")}>返回首页</button>
          </div>
        ) : model ? (
          <Survey model={model} />
        ) : (
          <p className="empty-text">加载中…</p>
        )}
      </div>
    </AppShell>
  );
}
