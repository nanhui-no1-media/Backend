"""问卷导出单元测试：统计聚合 + CSV / PDF 生成（activities/survey_export.py）。

JSON 导出已移除；多份问卷支持聚合为单个文件。
"""
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

    def _make_second(self):
        q2 = Questionnaire.objects.create(
            kind=Questionnaire.KIND_SURVEY,
            schema={**_schema(), "title": "第二份问卷"},
        )
        QuestionnaireResponse.objects.create(questionnaire=q2, answers={"grade": "高一", "note": "ok"})
        return q2

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

    def test_stats_csv_single(self):
        data, content_type, filename = survey_export.export_stats([self.q], "csv")
        text = data.decode("utf-8-sig")
        self.assertIn("年级", text)
        self.assertIn("高一", text)
        self.assertEqual(filename, f"survey-stats-{self.q.pk}.csv")
        self.assertIn("text/csv", content_type)

    def test_stats_json_removed(self):
        with self.assertRaises(ValueError):
            survey_export.export_stats([self.q], "json")

    def test_stats_pdf_single(self):
        data, content_type, filename = survey_export.export_stats([self.q], "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertEqual(content_type, "application/pdf")
        self.assertEqual(filename, f"survey-stats-{self.q.pk}.pdf")

    def test_stats_csv_multi(self):
        q2 = self._make_second()
        data, content_type, filename = survey_export.export_stats([self.q, q2], "csv")
        text = data.decode("utf-8-sig")
        self.assertTrue(text.splitlines()[0].startswith("问卷"))  # 多份时首列为「问卷」
        self.assertIn("第二份问卷", text)
        self.assertIn("batch-2", filename)

    def test_stats_pdf_multi(self):
        q2 = self._make_second()
        data, content_type, filename = survey_export.export_stats([self.q, q2], "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertIn("batch-2", filename)

    # ---- 作答导出 ----

    def test_responses_csv_single(self):
        data, content_type, filename = survey_export.export_responses([self.q], "csv")
        text = data.decode("utf-8-sig")
        self.assertIn("stu", text)
        self.assertIn("高一", text)
        self.assertIn("访客", text)  # 无 user 无 device 的匿名行
        self.assertEqual(filename, f"survey-responses-{self.q.pk}.csv")

    def test_responses_json_removed(self):
        with self.assertRaises(ValueError):
            survey_export.export_responses([self.q], "json")

    def test_responses_pdf_single(self):
        data, content_type, filename = survey_export.export_responses([self.q], "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertEqual(content_type, "application/pdf")

    def test_responses_csv_multi(self):
        q2 = self._make_second()
        data, content_type, filename = survey_export.export_responses([self.q, q2], "csv")
        text = data.decode("utf-8-sig")
        self.assertIn("问卷：测试问卷", text)
        self.assertIn("问卷：第二份问卷", text)
        self.assertIn("batch-2", filename)

    def test_responses_pdf_multi(self):
        q2 = self._make_second()
        data, content_type, filename = survey_export.export_responses([self.q, q2], "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertIn("batch-2", filename)
