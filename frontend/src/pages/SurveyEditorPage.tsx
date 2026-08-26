import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SurveyCreator, SurveyCreatorComponent } from "survey-creator-react";
import "survey-core/survey-core.css";
import "survey-creator-core/survey-creator-core.css";
import { SURVEY_LOCALE } from "../utils/surveyCreatorLocale";
import AppShell from "../components/AppShell";
import { api } from "../api/client";
import { activityApi } from "../api/activities";
import "../styles/detail.css";
import "../styles/form.css";

export default function SurveyEditorPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const activityId = Number(id);
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [creator, setCreator] = useState<SurveyCreator | null>(null);
  const [title, setTitle] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "编辑问卷";
    let alive = true;
    Promise.all([api.me(), activityApi.get(activityId)])
      .then(([me, a]: [any, Awaited<ReturnType<typeof activityApi.get>>]) => {
        if (!alive) return;
        if (a.type !== "survey") {
          setAllowed(false);
          setError("仅调研可编辑问卷。");
          return;
        }
        const uid = me.user?.id;
        const can = a.creator?.id === uid || !!me.user?.permissions?.can_change_activity;
        const schemaOk =
          a.status === "scheduled" || (a.status === "open" && (a.response_count ?? 0) === 0);
        if (!can) {
          setAllowed(false);
          setError("没有编辑权限。");
          return;
        }
        if (!schemaOk) {
          setAllowed(false);
          setError("已有作答，问卷已锁定。");
          return;
        }
        setTitle(a.title);
        setAllowed(true);
        const c = new SurveyCreator({ showLogicTab: true, locale: SURVEY_LOCALE });
        c.JSON = a.schema || { title: "", pages: [{ name: "page1", elements: [] }] };
        setCreator(c);
      })
      .catch((e: any) => {
        if (!alive) return;
        setAllowed(false);
        setError(e?.message || "加载失败");
      });
    return () => {
      alive = false;
    };
  }, [activityId]);

  const save = async () => {
    if (!creator) return;
    setError("");
    try {
      await activityApi.update(activityId, { schema: creator.JSON });
      setMsg("已保存");
    } catch (e: any) {
      setError(e?.message || "保存失败");
    }
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
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动</a>
            <span className="sep">/</span>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate(`/activity/${activityId}`); }}>{title || "调研"}</a>
            <span className="sep">/</span>
            <span>编辑问卷</span>
          </nav>
          <div className="page-head-row">
            <h1>编辑问卷</h1>
            {status === "ok" && (
              <button className="btn btn-primary" onClick={save}>保存 Schema</button>
            )}
          </div>
          {msg && <p className="detail-sub">{msg}</p>}
        </div>
      </div>
      <div className="container">
        {error && <div className="alert alert-danger" style={{ margin: "var(--s-4) 0" }}><span>{error}</span></div>}
        {status === "ok" && creator && (
          <div style={{ height: "70vh", minHeight: 480 }}>
            <SurveyCreatorComponent creator={creator} />
          </div>
        )}
        {status === "loading" && !error && <p className="empty-text">加载中…</p>}
      </div>
    </AppShell>
  );
}
