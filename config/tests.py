"""配置与密钥卫生（#27）：env 化的设置项与模板的就地断言。

这里只钉「结构不变量」——限流 scope 存在、私有存储与公开 MEDIA_ROOT 隔离、
邮件后端选择函数的分支、.env.example 入库且含必要键。具体业务行为由各 app 的测试覆盖。
"""
import os
from pathlib import Path

from django.conf import settings
from django.test import TestCase


class SettingsHygieneTest(TestCase):
    def test_register_and_resend_throttle_scopes_exist(self):
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertIn("register", rates)
        self.assertIn("resend_verification", rates)

    def test_private_media_root_is_separate_from_public_media(self):
        # 身份证明等审计留底绝不能落在公开 MEDIA_ROOT 之内（DEBUG 下后者被整目录公开服务）。
        private = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
        media = Path(settings.MEDIA_ROOT).resolve()
        self.assertNotEqual(private, media)
        self.assertNotEqual(private, media.parent)  # 不能恰好是 media 的父目录
        self.assertFalse(private.is_relative_to(media))

    def test_email_backend_helper(self):
        from config import settings as cfg

        self.assertEqual(
            cfg._email_backend_for(""),
            "django.core.mail.backends.console.ConsoleEmailBackend",
        )
        self.assertEqual(
            cfg._email_backend_for("someone@163.com"),
            "django.core.mail.backends.smtp.EmailBackend",
        )

    def test_allowed_hosts_parser(self):
        from config import settings as cfg

        self.assertEqual(cfg._parse_allowed_hosts(""), [])
        self.assertEqual(cfg._parse_allowed_hosts("a.com, b.com ,c.com"), ["a.com", "b.com", "c.com"])

    def test_secret_key_uses_dev_fallback_when_env_unset(self):
        # 证明 SECRET_KEY 走 env 读取 + dev 占位回退（生产用 .env 覆盖）。
        if os.environ.get("SECRET_KEY"):
            self.skipTest("SECRET_KEY 已在环境里显式设置，跳过回退断言")
        self.assertTrue(settings.SECRET_KEY)
        self.assertTrue(settings.SECRET_KEY.startswith("django-insecure-"))

    def test_env_example_committed_with_required_keys(self):
        # .env.example 必须入库且覆盖全部需保密/可配置项。
        example = Path(settings.BASE_DIR) / ".env.example"
        self.assertTrue(example.exists(), ".env.example 必须入库")
        text = example.read_text(encoding="utf-8")
        for key in (
            "SECRET_KEY",
            "DJANGO_DEBUG",
            "ALLOWED_HOSTS",
            "FRONTEND_URL",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "TURNSTILE_SITE_KEY",
            "TURNSTILE_SECRET_KEY",
        ):
            self.assertIn(key, text, f".env.example 缺少 {key}")
