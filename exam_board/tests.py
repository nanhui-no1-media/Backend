import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import ExamData


class UploadDataAuthTest(TestCase):
    """#33：POST /exam_board/upload/ 必须登录，且恢复 CSRF 保护。"""

    def setUp(self):
        self.user = User.objects.create_user(username="info", password="p")

    def _payload(self):
        return json.dumps(
            {"exam_date": "2026-06-01", "exam_title": "期中考试", "exam_list": "语文 数学 英语"}
        )

    def test_anonymous_upload_rejected(self):
        # 默认 Client 不强制 CSRF；匿名直达视图 → 401（修复前可匿名建数据）。
        resp = self.client.post(
            "/exam_board/upload/", data=self._payload(), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(ExamData.objects.count(), 0)

    def test_authenticated_upload_accepted(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            "/exam_board/upload/", data=self._payload(), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ExamData.objects.count(), 1)
        self.assertEqual(ExamData.objects.first().exam_title, "期中考试")

    def test_csrf_protection_restored(self):
        # @csrf_exempt 已移除：强制 CSRF 检查下，无 token 的（已登录）POST → 403，
        # 而非绕过 CSRF 直达视图。
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.user)
        resp = c.post(
            "/exam_board/upload/", data=self._payload(), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(ExamData.objects.count(), 0)

    def test_read_data_still_public(self):
        # read_data（公开展示用）保持公开读取，不在本次安全修复范围。
        ExamData.objects.create(exam_date="d", exam_title="t", exam_list="l")
        resp = self.client.get("/exam_board/read/")
        self.assertEqual(resp.status_code, 200)
