"""自助注册（#28）：建号 tracer bullet 的端到端测试。

覆盖：合法注册建 User+Profile(未验证)+IdentityProof 并发验证邮件；各类非法输入；
注册限流；证明材料存私有存储、不经公开 MEDIA_URL 暴露；profile 默认信任态。
"""
from pathlib import Path

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import IdentityProof, Profile

# 1x1 透明 PNG（合法图片，Pillow 可读）。
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c63f8cf00000003000100184bbb6e0000000049454e44ae426082"
)


def proof(name="proof.png", content_type="image/png"):
    return SimpleUploadedFile(name, PNG_BYTES, content_type=content_type)


def valid_payload(**overrides):
    """一份合法注册 payload（multipart），允许覆写单个字段。"""
    files = overrides.pop("proof_files", [proof()])
    base = {
        "username": "newbie",
        "password": "StrongPass123!",
        "password2": "StrongPass123!",
        "real_name": "张三",
        "identity": "student",
        "email": "newbie@example.com",
        "turnstile_token": "dummy",
    }
    base.update(overrides)
    return base, files


class RegisterViewTest(TestCase):
    def setUp(self):
        cache.clear()  # 注册限流按 IP 计数；隔离每个用例。

    def post(self, fields, files=None):
        data = dict(fields)
        if files:
            data["proof_files"] = files
        return self.client.post("/auth/register/", data=data)

    # ---- 合法注册 ----
    def test_register_success_creates_user_profile_proof_and_emails(self):
        fields, files = valid_payload()
        resp = self.post(fields, files)
        self.assertEqual(resp.status_code, 201, resp.content)

        user = User.objects.get(username="newbie")
        self.assertEqual(user.email, "newbie@example.com")  # 小写归一化
        self.assertTrue(user.is_active)
        # 自助注册：显式未验证（profile 默认 True 的信任态被 register 覆盖）
        self.assertFalse(user.profile.email_verified)
        self.assertFalse(user.profile.identity_verified)
        self.assertEqual(user.profile.real_name, "张三")
        self.assertEqual(user.profile.identity, "student")
        # IdentityProof 已建，1 条
        self.assertEqual(IdentityProof.objects.filter(user=user).count(), 1)
        # 验证邮件已发（dev console backend → mail.outbox）
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("newbie@example.com", mail.outbox[0].to)
        self.assertIn("/#/verify-email?uid=", mail.outbox[0].body)

    def test_multiple_proofs_accepted(self):
        fields, _ = valid_payload()
        resp = self.post(fields, [proof(), proof("p2.png"), proof("p3.png")])
        self.assertEqual(resp.status_code, 201, resp.content)
        user = User.objects.get(username="newbie")
        self.assertEqual(IdentityProof.objects.filter(user=user).count(), 3)

    # ---- 唯一性 ----
    def test_duplicate_username_rejected(self):
        fields, files = valid_payload()
        self.post(fields, files)  # 第一次成功
        fields2, files2 = valid_payload(username="newbie", email="other@example.com")
        resp = self.post(fields2, files2)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("用户名", str(resp.json()["error"]))

    def test_duplicate_username_case_insensitive_rejected(self):
        fields, files = valid_payload()
        self.post(fields, files)
        fields2, files2 = valid_payload(username="Newbie", email="other@example.com")
        resp = self.post(fields2, files2)
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_email_case_insensitive_rejected_and_normalized(self):
        fields, files = valid_payload(email="user@example.com")
        self.post(fields, files)
        # 不同大小写邮箱 + 不同用户名 → 仍判重
        fields2, files2 = valid_payload(username="another", email="USER@Example.COM")
        resp = self.post(fields2, files2)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("邮箱", str(resp.json()["error"]))
        # 原账号邮箱小写存储
        self.assertEqual(User.objects.get(username="newbie").email, "user@example.com")

    # ---- 字段校验 ----
    def test_invalid_identity_rejected(self):
        fields, files = valid_payload(identity="teacher")
        self.assertEqual(self.post(fields, files).status_code, 400)

    def test_password_mismatch_rejected(self):
        fields, files = valid_payload(password2="DifferentPass1!")
        self.assertEqual(self.post(fields, files).status_code, 400)

    def test_weak_password_rejected(self):
        fields, files = valid_payload(password="12345678", password2="12345678")
        resp = self.post(fields, files)
        self.assertEqual(resp.status_code, 400)

    def test_empty_password_rejected(self):
        # 修复前：password="" / password2="" 会绕过 validate_password（if password 守卫）
        # 且 create_user(password="") 建 unusable 账号；现须显式 400。
        fields, _ = valid_payload(password="", password2="")
        resp = self.post(fields, [proof()])
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(User.objects.filter(username="newbie").exists())

    def test_missing_real_name_rejected(self):
        fields, files = valid_payload(real_name="")
        self.assertEqual(self.post(fields, files).status_code, 400)

    # ---- 证明材料约束 ----
    def test_no_proof_rejected(self):
        fields, _ = valid_payload()
        resp = self.client.post("/auth/register/", data=fields)  # 不带 proof_files
        self.assertEqual(resp.status_code, 400)

    def test_too_many_proofs_rejected(self):
        fields, _ = valid_payload()
        resp = self.post(fields, [proof(f"p{i}.png") for i in range(4)])
        self.assertEqual(resp.status_code, 400)

    def test_oversize_proof_rejected(self):
        big = SimpleUploadedFile("big.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        fields, _ = valid_payload()
        resp = self.post(fields, [big])
        self.assertEqual(resp.status_code, 400)

    def test_wrong_content_type_rejected(self):
        bad = SimpleUploadedFile("proof.txt", b"not an image", content_type="text/plain")
        fields, _ = valid_payload()
        resp = self.post(fields, [bad])
        self.assertEqual(resp.status_code, 400)

    # ---- 限流 ----
    def test_throttle_blocks_after_daily_limit(self):
        # register scope = 5/day；空 POST 也计次（allow_request 在校验之前）。
        for i in range(5):
            self.assertEqual(self.client.post("/auth/register/", data={}).status_code, 400)
        resp = self.client.post("/auth/register/", data={})
        self.assertEqual(resp.status_code, 429)

    # ---- Turnstile 接线 ----
    @override_settings(DEBUG=False, TURNSTILE_SECRET_KEY="test-secret")
    def test_turnstile_failure_rejected_when_configured(self):
        # 不联网：直接 patch 校验函数返回 False，验证「失败 → 400」的接线。
        import accounts.views as views

        orig = views.verify_turnstile
        views.verify_turnstile = lambda token, ip="": False
        try:
            fields, files = valid_payload()
            resp = self.post(fields, files)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("人机校验", str(resp.json()["error"]))
        finally:
            views.verify_turnstile = orig


class IdentityProofStorageTest(TestCase):
    """证明材料落私有存储、不经公开 MEDIA_URL 暴露（#28 / #31 安全核心）。"""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="u", password="p", email="u@e.com")

    def test_proof_stored_under_private_media_not_public(self):
        proof_obj = IdentityProof.objects.create(user=self.user, file=proof())
        path = Path(proof_obj.file.path).resolve()
        private = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
        media = Path(settings.MEDIA_ROOT).resolve()
        self.assertTrue(path.is_relative_to(private))
        self.assertFalse(path.is_relative_to(media))

    def test_proof_not_served_via_public_media_url(self):
        proof_obj = IdentityProof.objects.create(user=self.user, file=proof("x.png"))
        # 公开 MEDIA_URL 前缀下 GET 该文件名 → 不应 200（私有存储不在 static(MEDIA_URL) 之下）
        url = settings.MEDIA_URL + "identity_proofs/x.png"
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)


class ProfileDefaultTrustTest(TestCase):
    """默认信任态：直接建的 profile 视为已验证（历史/admin 账号保持 Tier-3）。"""

    def test_directly_created_profile_is_verified(self):
        u = User.objects.create_user(username="legacy", password="p")
        p = Profile.objects.create(user=u)
        self.assertTrue(p.email_verified)
        self.assertTrue(p.identity_verified)
