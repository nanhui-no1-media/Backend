"""Site policy singleton: defaults, cache invalidation, public GET."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from common.models import SiteSettings
from common.policy import (
    DEFAULT_FEEDBACK_ANON_PER_IP_PER_DAY,
    DEFAULT_REGISTER_PER_IP_PER_DAY,
    DEFAULT_RESEND_VERIFICATION_PER_IP_PER_HOUR,
    DEFAULT_SYNC_UPLOAD_MAX_BYTES,
    DEFAULT_TUS_MEDIA_MAX_BYTES,
    get_policy,
    invalidate_policy_cache,
)


class SitePolicyDefaultsTest(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_missing_row_returns_today_hardcoded_defaults(self):
        self.assertFalse(SiteSettings.objects.exists())
        p = get_policy()
        self.assertTrue(p.verification_enabled)
        self.assertTrue(p.registration_enabled)
        self.assertEqual(p.register_per_ip_per_day, DEFAULT_REGISTER_PER_IP_PER_DAY)
        self.assertEqual(
            p.resend_verification_per_ip_per_hour,
            DEFAULT_RESEND_VERIFICATION_PER_IP_PER_HOUR,
        )
        self.assertEqual(p.feedback_anon_per_ip_per_day, DEFAULT_FEEDBACK_ANON_PER_IP_PER_DAY)
        self.assertEqual(p.sync_upload_max_bytes, DEFAULT_SYNC_UPLOAD_MAX_BYTES)
        self.assertEqual(p.tus_media_max_bytes, DEFAULT_TUS_MEDIA_MAX_BYTES)

    def test_save_always_pk_1_and_invalidates_cache(self):
        get_policy()  # warm cache with defaults
        SiteSettings(pk=2, verification_enabled=False).save()
        self.assertTrue(SiteSettings.objects.filter(pk=1).exists())
        self.assertFalse(SiteSettings.objects.filter(pk=2).exists())
        self.assertFalse(get_policy().verification_enabled)

    def test_delete_is_noop(self):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        obj.delete()
        self.assertTrue(SiteSettings.objects.filter(pk=1).exists())

    def test_invalidate_then_reread(self):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        obj.register_per_ip_per_day = 1
        obj.save()
        self.assertEqual(get_policy().register_per_ip_per_day, 1)
        SiteSettings.objects.filter(pk=1).update(register_per_ip_per_day=9)
        # queryset.update skips Model.save → cache stale until explicit drop
        self.assertEqual(get_policy().register_per_ip_per_day, 1)
        invalidate_policy_cache()
        self.assertEqual(get_policy().register_per_ip_per_day, 9)


class SitePolicyPublicGetTest(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_anonymous_get_returns_snapshot(self):
        resp = APIClient().get("/site-policy/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["verification_enabled"], True)
        self.assertEqual(data["registration_enabled"], True)
        self.assertEqual(data["register_per_ip_per_day"], 5)
        self.assertEqual(data["resend_verification_per_ip_per_hour"], 5)
        self.assertEqual(data["feedback_anon_per_ip_per_day"], 10)
        self.assertEqual(data["sync_upload_max_bytes"], 50 * 1024 * 1024)
        self.assertEqual(data["tus_media_max_bytes"], 500 * 1024 * 1024)

    def test_get_reflects_saved_row(self):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        obj.verification_enabled = False
        obj.sync_upload_max_bytes = 1024
        obj.save()
        data = APIClient().get("/site-policy/").json()
        self.assertFalse(data["verification_enabled"])
        self.assertEqual(data["sync_upload_max_bytes"], 1024)
