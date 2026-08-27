"""Django admin SurveyJS editor + results dashboard for 问卷 / 问卷结果."""
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import Activity, Questionnaire, QuestionnaireResponse


class QuestionnaireAdminDashboardTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "a@e.com", "x")
        self.staff = User.objects.create_user("st", password="x", is_staff=True)
        self.survey = Activity.objects.create(
            type="survey",
            status="open",
            title="后台调研",
        )
        self.survey.questionnaire.schema = {"title": "T", "pages": [{"name": "page1", "elements": []}]}
        self.survey.questionnaire.save()
        self.other = Activity.objects.create(
            type="deliberation",
            status="open",
            title="后台众议",
        )
        self.join = Questionnaire.get_join()

    def _client(self, user=None):
        c = Client()
        c.force_login(user or self.admin)
        return c

    def test_activity_change_form_has_no_survey_buttons(self):
        c = self._client()
        survey_page = c.get(f"/admin/activities/activity/{self.survey.pk}/change/")
        self.assertEqual(survey_page.status_code, 200)
        body = survey_page.content.decode()
        self.assertNotIn("编辑问卷", body)
        self.assertNotIn(f"/admin/activities/activity/{self.survey.pk}/survey-editor/", body)

    def test_questionnaire_change_form_has_editor_and_stats(self):
        c = self._client()
        q = self.survey.questionnaire
        page = c.get(f"/admin/activities/questionnaire/{q.pk}/change/")
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertIn("编辑问卷", body)
        self.assertIn("统计", body)
        self.assertIn(f"/admin/activities/questionnaire/{q.pk}/survey-editor/", body)
        self.assertIn(f"/admin/activities/questionnaire/{q.pk}/survey-results/", body)

    def test_editor_and_results_pages(self):
        c = self._client()
        q = self.survey.questionnaire
        editor = c.get(f"/admin/activities/questionnaire/{q.pk}/survey-editor/")
        self.assertEqual(editor.status_code, 200)
        html = editor.content.decode()
        self.assertIn("survey-creator-js.min.js", html)
        self.assertIn("survey-creator.i18n.zh-cn.min.js", html)
        self.assertIn("保存问卷", html)

        results = c.get(f"/admin/activities/questionnaire/{q.pk}/survey-results/")
        self.assertEqual(results.status_code, 200)
        rhtml = results.content.decode()
        self.assertIn("survey.analytics.min.js", rhtml)
        self.assertIn("analytics-zh-cn.js", rhtml)
        self.assertIn("chart.umd.min.js", rhtml)
        self.assertIn("暂无作答", rhtml)

    def test_save_schema_then_lock_after_response(self):
        c = self._client()
        q = self.survey.questionnaire
        url = f"/admin/activities/questionnaire/{q.pk}/survey-editor/"
        payload = {"schema": {"title": "改过", "pages": [{"name": "page1", "elements": []}]}}
        resp = c.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        q.refresh_from_db()
        self.assertEqual(q.schema["title"], "改过")

        QuestionnaireResponse.objects.create(questionnaire=q, answers={"q": 1})
        locked = c.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(locked.status_code, 400)
        self.assertFalse(locked.json()["ok"])

    def test_staff_without_model_perm_is_403(self):
        c = self._client(self.staff)
        q = self.survey.questionnaire
        resp = c.get(f"/admin/activities/questionnaire/{q.pk}/survey-editor/")
        self.assertEqual(resp.status_code, 403)

    def test_questionnaire_response_registered(self):
        q = self.survey.questionnaire
        row = QuestionnaireResponse.objects.create(
            questionnaire=q, user=self.admin, answers={"q": "a"},
        )
        c = self._client()
        listing = c.get("/admin/activities/questionnaireresponse/")
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "统计")
        change = c.get(f"/admin/activities/questionnaireresponse/{row.pk}/change/")
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, "统计")
        self.assertContains(
            change,
            f"/admin/activities/questionnaire/{q.pk}/survey-results/",
        )

    def test_join_questionnaire_admin_editor(self):
        c = self._client()
        pk = self.join.pk
        page = c.get(f"/admin/activities/questionnaire/{pk}/change/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("编辑问卷", page.content.decode())
        payload = {"schema": {"title": "加入改", "pages": [{"name": "page1", "elements": []}]}}
        saved = c.post(
            f"/admin/activities/questionnaire/{pk}/survey-editor/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200)
        self.join.refresh_from_db()
        self.assertEqual(self.join.schema["title"], "加入改")
