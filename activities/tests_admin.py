"""Django admin SurveyJS editor + results dashboard for 问卷 / 问卷结果."""
import json

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import Client, RequestFactory, TestCase

from .admin import ActivityAdmin
from .lifecycle import ARCHIVED, COLLECTING, OPEN
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
        self.assertIn("admin/surveyjs/isolate.css", html)
        self.assertIn("surveyjs-admin-host", html)
        self.assertIn("保存问卷", html)

        results = c.get(f"/admin/activities/questionnaire/{q.pk}/survey-results/")
        self.assertEqual(results.status_code, 200)
        rhtml = results.content.decode()
        self.assertIn("survey.analytics.min.js", rhtml)
        self.assertIn("admin/surveyjs/isolate.css", rhtml)
        self.assertIn("surveyjs-admin-host", rhtml)
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
        self.assertContains(listing, "查看作答")
        self.assertContains(
            listing,
            f"/admin/activities/questionnaireresponse/{row.pk}/survey-view/",
        )
        change = c.get(f"/admin/activities/questionnaireresponse/{row.pk}/change/")
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, "统计")
        self.assertContains(change, "查看作答")
        self.assertContains(
            change,
            f"/admin/activities/questionnaire/{q.pk}/survey-results/",
        )
        self.assertContains(
            change,
            f"/admin/activities/questionnaireresponse/{row.pk}/survey-view/",
        )

    def test_single_response_view_renders_surveyjs_display(self):
        q = self.survey.questionnaire
        row = QuestionnaireResponse.objects.create(
            questionnaire=q, user=self.admin, answers={"q": "hello"},
        )
        c = self._client()
        page = c.get(f"/admin/activities/questionnaireresponse/{row.pk}/survey-view/")
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("survey-js-ui.min.js", html)
        self.assertIn("survey.core.min.js", html)
        self.assertIn("survey-core.min.css", html)
        self.assertIn("admin/surveyjs/response.js", html)
        self.assertIn("admin/surveyjs/isolate.css", html)
        self.assertIn("surveyjs-admin-host", html)
        self.assertIn("查看作答", html)
        self.assertIn("hello", html)
        self.assertIn(self.admin.username, html)
        self.assertIn(f"/admin/activities/questionnaire/{q.pk}/survey-results/", html)

        results = c.get(f"/admin/activities/questionnaire/{q.pk}/survey-results/")
        self.assertEqual(results.status_code, 200)
        rhtml = results.content.decode()
        self.assertIn("查看作答", rhtml)
        self.assertIn(
            f"/admin/activities/questionnaireresponse/{row.pk}/survey-view/",
            rhtml,
        )
        self.assertNotIn(
            f"/admin/activities/questionnaireresponse/{row.pk}/change/",
            rhtml,
        )

    def test_staff_without_response_perm_cannot_view_single_response(self):
        q = self.survey.questionnaire
        row = QuestionnaireResponse.objects.create(
            questionnaire=q, user=self.admin, answers={"q": "a"},
        )
        c = self._client(self.staff)
        resp = c.get(f"/admin/activities/questionnaireresponse/{row.pk}/survey-view/")
        self.assertEqual(resp.status_code, 403)

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


class ActivityAdminArchiveTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="x")
        self.staff = User.objects.create_user(username="staff", password="x")
        self.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="activities", codename="change_activity"),
        )
        self.staff = User.objects.get(pk=self.staff.pk)
        self.collection = Activity.objects.create(
            type="collection", status=COLLECTING, title="待归档征集", creator=self.owner,
        )
        self.deliberation = Activity.objects.create(
            type="deliberation", status=OPEN, title="众议", creator=self.owner,
        )
        self.factory = RequestFactory()
        self.ma = ActivityAdmin(Activity, admin.site)
        self.ma.message_user = lambda *a, **k: None

    def _req(self, user):
        req = self.factory.post("/")
        req.user = user
        return req

    def test_archives_collection_and_skips_deliberation(self):
        qs = Activity.objects.filter(pk__in=[self.collection.pk, self.deliberation.pk])
        self.ma.archive_selected(self._req(self.staff), qs)
        self.collection.refresh_from_db()
        self.deliberation.refresh_from_db()
        self.assertEqual(self.collection.status, ARCHIVED)
        self.assertEqual(self.deliberation.status, OPEN)

    def test_hidden_without_change_perm(self):
        self.ma.archive_selected(
            self._req(self.owner),
            Activity.objects.filter(pk=self.collection.pk),
        )
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.status, COLLECTING)
