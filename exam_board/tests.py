from datetime import date

from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from exam_board.models import ExamData


def _writer():
    user = User.objects.create_user(username="info", password="x")
    user.user_permissions.add(Permission.objects.get(codename="add_examdata"))
    return user


class ExamReadTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        ExamData.objects.create(exam_date=date(2026, 1, 10), exam_title="期末", exam_list="语,数")
        ExamData.objects.create(exam_date=date(2026, 6, 15), exam_title="高考模拟", exam_list="语,数,英")

    def test_anon_lists_newest_first(self):
        resp = self.client.get("/exam_board/exams/")
        self.assertEqual(resp.status_code, 200)
        titles = [row["exam_title"] for row in resp.data["results"]]
        self.assertEqual(titles[0], "高考模拟")

    def test_latest_returns_newest(self):
        resp = self.client.get("/exam_board/exams/latest/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["exam_title"], "高考模拟")
        self.assertEqual(resp.data["data"]["exam_list"], "语,数,英")

    def test_latest_empty(self):
        ExamData.objects.all().delete()
        resp = self.client.get("/exam_board/exams/latest/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["data"])


class ExamWritePermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.writer = _writer()
        self.normal = User.objects.create_user(username="normal", password="x")
        self.payload = {
            "exam_date": "2026-08-21",
            "exam_title": "开学考",
            "exam_list": "语文,数学,英语",
        }

    def test_anon_cannot_write(self):
        resp = self.client.post("/exam_board/exams/", self.payload, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_logged_in_without_perm_cannot_write(self):
        self.client.force_authenticate(self.normal)
        resp = self.client.post("/exam_board/exams/", self.payload, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_perm_holder_can_create(self):
        self.client.force_authenticate(self.writer)
        resp = self.client.post("/exam_board/exams/", self.payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["exam_title"], "开学考")
        self.assertEqual(ExamData.objects.count(), 1)

    def test_info_group_seed_has_write_perm(self):
        user = User.objects.create_user(username="g", password="x")
        grp, _ = Group.objects.get_or_create(name="信息组")
        user.groups.add(grp)
        self.assertTrue(user.has_perm("exam_board.add_examdata"))


class ExamValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(_writer())

    def test_empty_title_rejected(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {"exam_date": "2026-01-01", "exam_title": "  ", "exam_list": "语"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_date_rejected(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {"exam_title": "x", "exam_list": "语"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_title_too_long_rejected(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {"exam_date": "2026-01-01", "exam_title": "x" * 51, "exam_list": "语"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
