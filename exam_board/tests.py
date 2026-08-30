from datetime import date, time
from io import BytesIO

from django.contrib.auth.models import Group, Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from exam_board.models import Exam, ExamBatch, ExamErrata, ExamSubject


def _png(name="q.png"):
    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def _writer():
    user = User.objects.create_user(username="info", password="x")
    user.user_permissions.add(Permission.objects.get(codename="add_exam"))
    return user


def _exam(**overrides):
    exam = Exam.objects.create(title=overrides.pop("title", "期末"))
    batch = ExamBatch.objects.create(
        exam=exam, name=overrides.pop("batch_name", "高一"), sort_order=0,
    )
    ExamSubject.objects.create(
        batch=batch,
        name=overrides.pop("subject_name", "语文"),
        exam_date=overrides.pop("exam_date", date(2026, 1, 10)),
        start_time=overrides.pop("start_time", time(9, 0)),
        end_time=overrides.pop("end_time", time(11, 30)),
    )
    return exam


class ExamReadTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        first = _exam(title="月考")
        self.latest = _exam(title="期末", batch_name="高二")
        self.assertGreater(self.latest.id, first.id)

    def test_anon_lists_newest_first(self):
        resp = self.client.get("/exam_board/exams/")
        self.assertEqual(resp.status_code, 200)
        titles = [row["title"] for row in resp.data["results"]]
        self.assertEqual(titles[0], "期末")
        self.assertEqual(resp.data["results"][0]["batch_count"], 1)

    def test_latest_returns_newest_with_subjects(self):
        resp = self.client.get("/exam_board/exams/latest/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data["data"]
        self.assertEqual(data["title"], "期末")
        self.assertEqual(data["batches"][0]["name"], "高二")
        self.assertEqual(data["batches"][0]["subjects"][0]["name"], "语文")
        self.assertEqual(data["batches"][0]["subjects"][0]["start_time"], "09:00:00")

    def test_latest_empty(self):
        Exam.objects.all().delete()
        resp = self.client.get("/exam_board/exams/latest/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["data"])

    def test_clock_is_public(self):
        resp = self.client.get("/exam_board/exams/clock/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["timezone"], "Asia/Shanghai")
        self.assertIsInstance(resp.data["timestamp"], int)
        self.assertIn("+08:00", resp.data["iso"])


class ExamWritePermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.writer = _writer()
        self.normal = User.objects.create_user(username="normal", password="x")
        self.payload = {
            "title": "开学考",
            "batches": [
                {
                    "name": "高一",
                    "sort_order": 0,
                    "subjects": [
                        {
                            "name": "语文",
                            "exam_date": "2026-08-21",
                            "start_time": "09:00",
                            "end_time": "11:30",
                        },
                        {
                            "name": "数学",
                            "exam_date": "2026-08-21",
                            "start_time": "14:00",
                            "end_time": "16:00",
                        },
                    ],
                },
            ],
        }

    def test_anon_cannot_write(self):
        resp = self.client.post("/exam_board/exams/", self.payload, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_logged_in_without_perm_cannot_write(self):
        self.client.force_authenticate(self.normal)
        resp = self.client.post("/exam_board/exams/", self.payload, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_perm_holder_can_create_nested(self):
        self.client.force_authenticate(self.writer)
        resp = self.client.post("/exam_board/exams/", self.payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["title"], "开学考")
        self.assertEqual(len(resp.data["batches"]), 1)
        self.assertEqual(len(resp.data["batches"][0]["subjects"]), 2)
        self.assertEqual(Exam.objects.count(), 1)
        self.assertEqual(ExamSubject.objects.count(), 2)

    def test_update_replaces_batches(self):
        self.client.force_authenticate(self.writer)
        exam = _exam()
        resp = self.client.put(
            f"/exam_board/exams/{exam.pk}/",
            {
                "title": "期末改",
                "batches": [
                    {
                        "name": "高三",
                        "subjects": [
                            {
                                "name": "英语",
                                "exam_date": "2026-01-11",
                                "start_time": "08:00",
                                "end_time": "10:00",
                            },
                        ],
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["title"], "期末改")
        self.assertEqual(resp.data["batches"][0]["name"], "高三")
        self.assertEqual(ExamBatch.objects.filter(exam=exam).count(), 1)
        self.assertEqual(ExamSubject.objects.filter(batch__exam=exam).count(), 1)

    def test_info_group_seed_has_write_perm(self):
        user = User.objects.create_user(username="g", password="x")
        grp, _ = Group.objects.get_or_create(name="信息组")
        user.groups.add(grp)
        self.assertTrue(user.has_perm("exam_board.add_exam"))


class ExamValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(_writer())

    def test_empty_title_rejected(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {"title": "  ", "batches": [{"name": "高一", "subjects": []}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_batch_rejected(self):
        resp = self.client.post("/exam_board/exams/", {"title": "x", "batches": []}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_end_before_start_rejected(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {
                "title": "x",
                "batches": [{
                    "name": "高一",
                    "subjects": [{
                        "name": "语",
                        "exam_date": "2026-01-01",
                        "start_time": "11:00",
                        "end_time": "09:00",
                    }],
                }],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_overlapping_subjects_rejected(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {
                "title": "x",
                "batches": [{
                    "name": "高一",
                    "subjects": [
                        {
                            "name": "语",
                            "exam_date": "2026-01-01",
                            "start_time": "09:00",
                            "end_time": "11:30",
                        },
                        {
                            "name": "数",
                            "exam_date": "2026-01-01",
                            "start_time": "11:00",
                            "end_time": "13:00",
                        },
                    ],
                }],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_adjacent_subjects_allowed(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {
                "title": "x",
                "batches": [{
                    "name": "高一",
                    "subjects": [
                        {
                            "name": "语",
                            "exam_date": "2026-01-01",
                            "start_time": "09:00",
                            "end_time": "11:00",
                        },
                        {
                            "name": "数",
                            "exam_date": "2026-01-01",
                            "start_time": "11:00",
                            "end_time": "13:00",
                        },
                    ],
                }],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_duplicate_batch_names_rejected(self):
        resp = self.client.post(
            "/exam_board/exams/",
            {
                "title": "x",
                "batches": [
                    {"name": "高一", "subjects": []},
                    {"name": "高一", "subjects": []},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


class ExamErrataTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.writer = _writer()

    def test_current_empty(self):
        resp = self.client.get("/exam_board/errata/current/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["data"])

    def test_anon_cannot_publish(self):
        resp = self.client.post("/exam_board/errata/", {"text": "第3题更正"}, format="multipart")
        self.assertEqual(resp.status_code, 403)

    def test_publish_text_and_image(self):
        self.client.force_authenticate(self.writer)
        image = _png()
        resp = self.client.post(
            "/exam_board/errata/",
            {"text": "第3题更正", "image": image},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["text"], "第3题更正")
        self.assertTrue(resp.data["image_url"])
        current = self.client.get("/exam_board/errata/current/")
        self.assertEqual(current.data["data"]["id"], resp.data["id"])

    def test_new_errata_replaces_previous(self):
        self.client.force_authenticate(self.writer)
        self.client.post("/exam_board/errata/", {"text": "旧"}, format="multipart")
        resp = self.client.post("/exam_board/errata/", {"text": "新"}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        current = self.client.get("/exam_board/errata/current/")
        self.assertEqual(current.data["data"]["text"], "新")
        self.assertEqual(ExamErrata.objects.filter(dismissed_at__isnull=True).count(), 1)

    def test_dismiss_clears_current(self):
        self.client.force_authenticate(self.writer)
        self.client.post("/exam_board/errata/", {"text": "误"}, format="multipart")
        resp = self.client.post("/exam_board/errata/dismiss/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["dismissed"], 1)
        current = self.client.get("/exam_board/errata/current/")
        self.assertIsNone(current.data["data"])

    def test_empty_errata_rejected(self):
        self.client.force_authenticate(self.writer)
        resp = self.client.post("/exam_board/errata/", {"text": "  "}, format="multipart")
        self.assertEqual(resp.status_code, 400)
