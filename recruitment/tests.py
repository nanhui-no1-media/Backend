from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from recruitment.models import JoinQuestionnaire, JoinResponse, RecruitmentNotice


def _editor():
    user = User.objects.create_user(username="editor", password="x")
    user.user_permissions.add(Permission.objects.get(codename="change_aboutpage"))
    return user


class RecruitmentLandingTest(TestCase):
    def test_anon_reads_notice_and_schema(self):
        resp = APIClient().get("/recruitment/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("notice", resp.data)
        self.assertIn("schema", resp.data)
        self.assertIn("pages", resp.data["schema"])
        self.assertTrue(any(t.get("type") == "skip" for t in resp.data["schema"].get("triggers") or []))


class NoticeAckGateTest(TestCase):
    def test_submit_without_ack_rejected(self):
        resp = APIClient().post(
            "/recruitment/responses/",
            {"answers": {"grade": "高一"}, "notice_acknowledged": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_submit_with_ack_persists(self):
        resp = APIClient().post(
            "/recruitment/responses/",
            {"answers": {"grade": "高一", "intro": "你好"}, "notice_acknowledged": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["ok"])
        self.assertEqual(JoinResponse.objects.count(), 1)
        self.assertEqual(JoinResponse.objects.get().answers["grade"], "高一")

    def test_empty_answers_rejected(self):
        resp = APIClient().post(
            "/recruitment/responses/",
            {"answers": {}, "notice_acknowledged": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


class SchemaPersistTest(TestCase):
    def test_editor_updates_schema(self):
        client = APIClient()
        client.force_authenticate(_editor())
        schema = {"title": "新问卷", "pages": [{"name": "p", "elements": [{"type": "text", "name": "n"}]}]}
        resp = client.put("/recruitment/schema/", {"schema": schema}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(JoinQuestionnaire.objects.get_solo().schema["title"], "新问卷")

    def test_editor_updates_notice(self):
        client = APIClient()
        client.force_authenticate(_editor())
        resp = client.put("/recruitment/notice/", {"content": "<p>2026 招生</p>"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RecruitmentNotice.objects.get_solo().content, "<p>2026 招生</p>")

    def test_invalid_schema_rejected(self):
        client = APIClient()
        client.force_authenticate(_editor())
        resp = client.put("/recruitment/schema/", {"schema": {"title": "无 pages"}}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_stranger_cannot_edit_schema(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(username="u", password="x"))
        resp = client.put("/recruitment/schema/", {"schema": {"pages": []}}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_stranger_cannot_list_responses(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(username="u", password="x"))
        self.assertEqual(client.get("/recruitment/responses/").status_code, 403)
