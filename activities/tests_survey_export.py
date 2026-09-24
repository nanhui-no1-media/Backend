"""问卷导出单元测试：统计聚合 + CSV / JSON / PDF 生成（activities/survey_export.py）。"""
import json

from django.contrib.auth.models import User
from django.test import TestCase

from . import survey_export
from .models import Questionnaire, QuestionnaireResponse


def _schema():
    return {
        "title": "测试问卷",
        "pages": [{
            "name": "p1",
            "elements": [
                {"type": "radiogroup", "name": "grade", "title": "年级", "choices": ["高一", "高二"]},
                {"type": "checkbox", "name": "skills", "title": "方向", "choices": ["摄影", "剪辑"]},
                {"type": "rating", "name": "score", "title": "评分"},
                {"type": "text", "name": "note", "title": "备注"},
                {"type": "file", "name": "attach", "title": "作品"},
            ],
        }],
    }


class SurveyExportTest(TestCase):
    def setUp(self):
        self.q = Questionnaire.objects.create(kind=Questionnaire.KIND_SURVEY, schema=_schema())
        self.u = User.objects.create_user(username="stu", password="x")
        QuestionnaireResponse.objects.create(
            questionnaire=self.q, user=self.u,
            answers={
                "grade": "高一", "skills": ["摄影", "剪辑"], "score": 4, "note": "你好",
                "attach": [{"name": "a.png", "content": "https://x/a.png"}],
            },
        )
        QuestionnaireResponse.objects.create(
            questionnaire=self.q,
            answers={"grade": "高二", "skills": ["摄影"], "score": 5},
        )

    # ---- 聚合 ----

    def test_stats_aggregates(self):
        stats = survey_export.compute_stats(_schema(), [r.answers for r in self.q.responses.all()])
        by_name = {s["name"]: s for s in stats}
        self.assertEqual(by_name["grade"]["counts"]["高一"], 1)
        self.assertEqual(by_name["grade"]["counts"]["高二"], 1)
        self.assertEqual(by_name["skills"]["counts"]["摄影"], 2)
        self.assertEqual(by_name["skills"]["counts"]["剪辑"], 1)
        self.assertEqual(by_name["score"]["average"], 4.5)
        self.assertEqual(by_name["note"]["answers"], ["你好"])

    # ---- 统计导出 ----

    def test_stats_csv(self):
        data, content_type, filename = survey_export.export_stats(self.q, "csv")
        text = data.decode("utf-8-sig")
        self.assertIn("年级", text)
        self.assertIn("高一", text)
        self.assertTrue(filename.endswith(".csv"))
        self.assertIn("text/csv", content_type)

    def test_stats_json(self):
        data, content_type, filename = survey_export.export_stats(self.q, "json")
        payload = json.loads(data)
        self.assertEqual(payload["response_count"], 2)
        self.assertEqual(len(payload["stats"]), 5)
        self.assertTrue(filename.endswith(".json"))

    def test_stats_pdf(self):
        data, content_type, filename = survey_export.export_stats(self.q, "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertEqual(content_type, "application/pdf")

    # ---- 作答导出 ----

    def test_responses_csv(self):
        data, content_type, filename = survey_export.export_responses(self.q, "csv")
        text = data.decode("utf-8-sig")
        self.assertIn("stu", text)
        self.assertIn("高一", text)
        self.assertIn("访客", text)  # 无 user 无 device 的匿名行

    def test_responses_json(self):
        data, content_type, filename = survey_export.export_responses(self.q, "json")
        payload = json.loads(data)
        self.assertEqual(len(payload["responses"]), 2)
        labels = [r["user_label"] for r in payload["responses"]]
        self.assertIn("stu", labels)

    def test_responses_pdf(self):
        data, content_type, filename = survey_export.export_responses(self.q, "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertEqual(content_type, "application/pdf")
