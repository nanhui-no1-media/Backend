import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import SurveyFill from "../components/SurveyFill";
import { recruitmentApi } from "../api/recruitment";
import "../styles/detail.css";

export default function JoinFormPage() {
  const navigate = useNavigate();
  const [schema, setSchema] = useState<Record<string, unknown> | null>(null);
  const [done, setDone] = useState("");
  const [already, setAlready] = useState(false);

  useEffect(() => {
    document.title = "自我介绍问卷";
    if (sessionStorage.getItem("join_notice_ack") !== "1") {
      navigate("/join", { replace: true });
      return;
    }
    recruitmentApi.landing().then((d) => {
      setSchema(d.schema);
      if (d.already_responded) setAlready(true);
    });
  }, [navigate]);

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/join"); }}>加入社团</a>
            <span className="sep">/</span>
            <span>自我介绍问卷</span>
          </nav>
          <h1>自我介绍问卷</h1>
        </div>
      </div>
      <div className="container">
        {already || done ? (
          <div className="card card-pad"><p>{done || "你已经提交过了。"}</p>
            <button className="btn btn-primary" onClick={() => navigate("/")}>返回首页</button>
          </div>
        ) : schema ? (
          <div className="card card-pad">
            <SurveyFill
              schema={schema}
              onComplete={async (answers) => {
                const res = await recruitmentApi.submit(answers, true);
                sessionStorage.removeItem("join_notice_ack");
                setDone(res.message || "报名已提交");
              }}
            />
          </div>
        ) : (
          <p className="empty-text">加载中…</p>
        )}
      </div>
    </AppShell>
  );
}
