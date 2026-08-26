import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SurveyCreator, SurveyCreatorComponent } from "survey-creator-react";
import "survey-core/survey-core.css";
import "survey-creator-core/survey-creator-core.css";
import { SURVEY_LOCALE } from "../utils/surveyCreatorLocale";
import AppShell from "../components/AppShell";
import { api } from "../api/client";
import { recruitmentApi } from "../api/recruitment";
import "../styles/detail.css";
import "../styles/form.css";

export default function JoinEditorPage() {
  const navigate = useNavigate();
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [creator, setCreator] = useState<SurveyCreator | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    document.title = "编辑问卷";
    api.me()
      .then((d: any) => setAllowed(!!d.user?.permissions?.can_edit_about))
      .catch(() => setAllowed(false));
  }, []);

  useEffect(() => {
    if (!allowed) return;
    let alive = true;
    recruitmentApi.getSchema().then((d) => {
      if (!alive) return;
      const c = new SurveyCreator({ showLogicTab: true, locale: SURVEY_LOCALE });
      c.JSON = d.schema;
      setCreator(c);
    });
    return () => { alive = false; };
  }, [allowed]);

  const save = async () => {
    if (!creator) return;
    await recruitmentApi.updateSchema(creator.JSON);
    setMsg("已保存");
  };

  const status = useMemo(() => {
    if (allowed === false) return "forbidden";
    if (!creator) return "loading";
    return "ok";
  }, [allowed, creator]);

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/join"); }}>加入社团</a>
            <span className="sep">/</span>
            <span>编辑问卷</span>
          </nav>
          <div className="page-head-row">
            <h1>编辑自我介绍问卷</h1>
            {status === "ok" && <button className="btn btn-primary" onClick={save}>保存 Schema</button>}
          </div>
          {msg && <p className="detail-sub">{msg}</p>}
        </div>
      </div>
      <div className="container">
        {status === "forbidden" && <div className="alert alert-danger">没有编辑权限。</div>}
        {status === "ok" && creator && (
          <div style={{ height: "70vh", minHeight: 480 }}>
            <SurveyCreatorComponent creator={creator} />
          </div>
        )}
      </div>
    </AppShell>
  );
}
