"""Django admin SurveyJS editor + results dashboard for 调研."""
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import Activity, SurveyResponse


class SurveyAdminDashboardTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "a@e.com", "x")
        self.staff = User.objects.create_user("st", password="x", is_staff=True)
        self.survey = Activity.objects.create(
            type="survey",
            status="open",
            title="后台调研",
            schema={"title": "T", "pages": [{"name": "page1", "elements": []}]},
        )
        self.other = Activity.objects.create(
            type="deliberation",
            status="open",
            title="后台众议",
        )

    def _client(self, user=None):
        c = Client()
        c.force_login(user or self.admin)
        return c

    def test_change_form_buttons_only_for_survey(self):
        c = self._client()
        survey_page = c.get(f"/admin/activities/activity/{self.survey.pk}/change/")
        self.assertEqual(survey_page.status_code, 200)
        body = survey_page.content.decode()
        self.assertIn("编辑问卷", body)
        self.assertIn("统计", body)
        self.assertIn(f"/admin/activities/activity/{self.survey.pk}/survey-editor/", body)
        self.assertIn(f"/admin/activities/activity/{self.survey.pk}/survey-results/", body)

        other_page = c.get(f"/admin/activities/activity/{self.other.pk}/change/")
        self.assertEqual(other_page.status_code, 200)
        self.assertNotIn("编辑问卷", other_page.content.decode())

    def test_editor_and_results_pages(self):
        c = self._client()
        editor = c.get(f"/admin/activities/activity/{self.survey.pk}/survey-editor/")
        self.assertEqual(editor.status_code, 200)
        html = editor.content.decode()
        self.assertIn("survey-creator-js.min.js", html)
        self.assertIn("survey-creator.i18n.zh-cn.min.js", html)
        self.assertIn("保存问卷", html)

        results = c.get(f"/admin/activities/activity/{self.survey.pk}/survey-results/")
        self.assertEqual(results.status_code, 200)
        rhtml = results.content.decode()
        self.assertIn("survey.analytics.min.js", rhtml)
        self.assertIn("analytics-zh-cn.js", rhtml)
        self.assertIn("chart.umd.min.js", rhtml)
        self.assertIn("暂无作答", rhtml)

    def test_editor_404_for_non_survey(self):
        c = self._client()
        resp = c.get(f"/admin/activities/activity/{self.other.pk}/survey-editor/")
        self.assertEqual(resp.status_code, 404)

    def test_save_schema_then_lock_after_response(self):
        c = self._client()
        url = f"/admin/activities/activity/{self.survey.pk}/survey-editor/"
        payload = {"schema": {"title": "改过", "pages": [{"name": "page1", "elements": []}]}}
        resp = c.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.schema["title"], "改过")

        SurveyResponse.objects.create(activity=self.survey, answers={"q": 1})
        locked = c.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(locked.status_code, 400)
        self.assertFalse(locked.json()["ok"])

    def test_staff_without_model_perm_is_403(self):
        c = self._client(self.staff)
        resp = c.get(f"/admin/activities/activity/{self.survey.pk}/survey-editor/")
        self.assertEqual(resp.status_code, 403)

    def test_survey_response_registered(self):
        row = SurveyResponse.objects.create(
            activity=self.survey, user=self.admin, answers={"q": "a"},
        )
        c = self._client()
        listing = c.get("/admin/activities/surveyresponse/")
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "后台调研")
        self.assertContains(listing, "统计")
        change = c.get(f"/admin/activities/surveyresponse/{row.pk}/change/")
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, "统计")
        self.assertContains(
            change,
            f"/admin/activities/activity/{self.survey.pk}/survey-results/",
        )
