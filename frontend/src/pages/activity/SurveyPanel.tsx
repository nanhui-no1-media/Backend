import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { activityApi } from "../../api/activities";
import SurveyFill from "../../components/SurveyFill";
import type { ActivityPanelProps } from "./types";

export default function SurveyPanel({
  a, setActivity, user, busy, setBusy, setError, canManage,
}: ActivityPanelProps & { canManage: boolean }) {
  const navigate = useNavigate();
  const canEditSchema = canManage && a.schema_editable;
  const surveyApproved = !a.review_status || a.review_status === "approved";
  const alreadySubmitted = a.my_response != null;
  const canFillSurvey =
    a.status === "open" &&
    surveyApproved &&
    !alreadySubmitted &&
    (a.audience === "public" || !!user);

  return (
    <div className="card card-pad" style={{ marginTop: "var(--s-4)" }}>
      <h3 className="section-h">问卷</h3>
      {canEditSchema && (
        <div style={{ marginBottom: 12 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/activity/${a.id}/survey-edit`)} disabled={busy}>编辑问卷</button>
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
      {canFillSurvey && (
        <SurveyFill
          schema={a.schema || { pages: [{ name: "page1", elements: [] }] }}
          onComplete={async (answers) => {
            setBusy(true); setError("");
            try {
              const updated = await activityApi.respond(a.id, answers);
              setActivity(updated);
            } catch (e: unknown) {
              setError(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        />
      )}
      {a.status === "closed" && (
        <p className="muted">征答已结束。{a.response_count != null ? `已收到 ${a.response_count} 份作答。` : ""}</p>
      )}
    </div>
  );
}
