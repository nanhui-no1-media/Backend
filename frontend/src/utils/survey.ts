import { Model } from "survey-core";
import { SURVEY_LOCALE } from "./surveyLocale";

/** Shared SurveyJS fill model: responsive width + a complete handler. Used by join and 调研. */
export function createSurveyModel(
  schema: Record<string, unknown>,
  onComplete: (answers: Record<string, unknown>) => void | Promise<void>,
): Model {
  const m = new Model(schema);
  m.locale = SURVEY_LOCALE;
  m.widthMode = "responsive";
  m.onComplete.add((sender) => {
    void onComplete(sender.data as Record<string, unknown>);
  });
  return m;
}
