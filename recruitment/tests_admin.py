"""Django admin SurveyJS editor + results dashboard for 自我介绍问卷."""
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import JoinQuestionnaire, JoinResponse


class JoinSurveyAdminDashboardTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "a@e.com", "x")
        self.questionnaire = JoinQuestionnaire.objects.get_solo()

    def _client(self):
        c = Client()
        c.force_login(self.admin)
        return c

    def test_change_form_buttons(self):
        c = self._client()
        pk = self.questionnaire.pk
        page = c.get(f"/admin/recruitment/joinquestionnaire/{pk}/change/")
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertIn("编辑问卷", body)
        self.assertIn("统计", body)
        self.assertIn(f"/admin/recruitment/joinquestionnaire/{pk}/survey-editor/", body)
        self.assertIn(f"/admin/recruitment/joinquestionnaire/{pk}/survey-results/", body)

    def test_editor_save_and_results(self):
        c = self._client()
        pk = self.questionnaire.pk
        editor = c.get(f"/admin/recruitment/joinquestionnaire/{pk}/survey-editor/")
        self.assertEqual(editor.status_code, 200)
        self.assertContains(editor, "survey-creator-js.min.js")

        payload = {"schema": {"title": "加入改", "pages": [{"name": "page1", "elements": []}]}}
        saved = c.post(
            f"/admin/recruitment/joinquestionnaire/{pk}/survey-editor/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200)
        self.assertTrue(saved.json()["ok"])
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.schema["title"], "加入改")

        JoinResponse.objects.create(user=self.admin, answers={"grade": "高一"})
        results = c.get(f"/admin/recruitment/joinquestionnaire/{pk}/survey-results/")
        self.assertEqual(results.status_code, 200)
        html = results.content.decode()
        self.assertIn("survey.analytics.min.js", html)
        self.assertIn("adm", html)

    def test_join_response_links_dashboard(self):
        row = JoinResponse.objects.create(user=None, answers={"intro": "hi"})
        c = self._client()
        listing = c.get("/admin/recruitment/joinresponse/")
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "统计")
        change = c.get(f"/admin/recruitment/joinresponse/{row.pk}/change/")
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, "统计")
        self.assertContains(
            change,
            f"/admin/recruitment/joinquestionnaire/{self.questionnaire.pk}/survey-results/",
        )
