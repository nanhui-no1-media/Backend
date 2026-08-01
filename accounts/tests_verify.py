"""邮箱验证解锁登录（#29）：verify-email / resend / 登录三态。"""
import json

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import Profile
from accounts.tokens import email_verification_token


def _login(client, **fields):
    return client.post("/auth/login/", data=json.dumps(fields), content_type="application/json")


def make_unverified_user(username="someone", email="someone@example.com", password="StrongPass123!"):
    u = User.objects.create_user(username=username, email=email, password=password, is_active=True)
    # 复刻 register 视图：显式未验证 profile
    Profile.objects.update_or_create(
        user=u, defaults={"email_verified": False, "identity_verified": False, "identity": "student"}
    )
    return u


class VerifyEmailViewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_unverified_user()
        self.password = "StrongPass123!"

    def _uid_token(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        return uid, email_verification_token.make_token(user)

    def test_verify_success_sets_email_verified(self):
        uid, token = self._uid_token(self.user)
        resp = self.client.get(f"/auth/verify-email/?uid={uid}&token={token}")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.email_verified)
        # 验证后可登录（Tier1→2）
        resp = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "someone", "password": self.password}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_verify_invalid_token_rejected(self):
        uid, _ = self._uid_token(self.user)
        resp = self.client.get(f"/auth/verify-email/?uid={uid}&token=bogus-token")
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)

    def test_verify_tampered_uid_rejected(self):
        _, token = self._uid_token(self.user)
        resp = self.client.get(f"/auth/verify-email/?uid=not-a-valid-uid&token={token}")
        self.assertEqual(resp.status_code, 400)

    def test_verify_after_email_change_old_token_invalid(self):
        uid, token = self._uid_token(self.user)
        self.user.email = "changed@example.com"
        self.user.save()
        resp = self.client.get(f"/auth/verify-email/?uid={uid}&token={token}")
        self.assertEqual(resp.status_code, 400)

    def test_verify_idempotent_when_already_verified(self):
        uid, token = self._uid_token(self.user)
        self.user.profile.email_verified = True
        self.user.profile.save(update_fields=["email_verified"])
        # 已验证：旧令牌随 email_verified 翻 True 而失效 → 400（不可重放）
        resp = self.client.get(f"/auth/verify-email/?uid={uid}&token={token}")
        self.assertEqual(resp.status_code, 400)


class ResendVerificationViewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_unverified_user()

    def test_resend_sends_for_unverified(self):
        resp = self.client.post(
            "/auth/resend-verification/",
            data=json.dumps({"email": "someone@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_no_leak_for_unknown_email(self):
        resp = self.client.post(
            "/auth/resend-verification/",
            data=json.dumps({"email": "nobody@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)  # 不发信，但提示一致

    def test_resend_no_leak_for_already_verified(self):
        self.user.profile.email_verified = True
        self.user.profile.save(update_fields=["email_verified"])
        resp = self.client.post(
            "/auth/resend-verification/",
            data=json.dumps({"email": "someone@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)  # 已验证，不重发

    def test_resend_throttled(self):
        for _ in range(5):
            self.client.post(
                "/auth/resend-verification/",
                data=json.dumps({"email": "someone@example.com"}),
                content_type="application/json",
            )
        resp = self.client.post(
            "/auth/resend-verification/",
            data=json.dumps({"email": "someone@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 429)


class LoginThreeStateTest(TestCase):
    """登录三态：未验证邮箱 / 已停用 / 凭证错——分别提示，错误密码不泄露状态。"""

    def setUp(self):
        cache.clear()

    def test_login_unverified_blocked_with_email(self):
        u = make_unverified_user("uv", "uv@example.com", "StrongPass123!")
        resp = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "uv", "password": "StrongPass123!"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertEqual(data["reason"], "email_not_verified")
        self.assertEqual(data["email"], "uv@example.com")

    def test_login_disabled_blocked(self):
        u = make_unverified_user("dis", "dis@example.com", "StrongPass123!")
        u.is_active = False
        u.save()
        resp = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "dis", "password": "StrongPass123!"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["reason"], "account_disabled")

    def test_wrong_password_does_not_leak_state(self):
        # 未验证账号 + 错误密码 → 401（不是 403），不暴露「未验证」状态
        make_unverified_user("uv", "uv@example.com", "StrongPass123!")
        resp = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "uv", "password": "wrong-password"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn("reason", resp.json())

    def test_existing_verified_user_login_unchanged(self):
        # 回归：无 profile 的存量用户（默认信任）仍可登录
        User.objects.create_user(username="legacy", password="StrongPass123!")
        resp = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "legacy", "password": "StrongPass123!"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
