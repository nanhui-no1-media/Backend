"""验证模型单元 + 迁移默认信任（ADR-0006）。

- ``is_verified``：纯计算（任一通道 approved 即真；匿名 / 无行 / pending / rejected ⇒ 假）。
- ``IsVerified`` 门禁：超级用户逃生舱（无 approved 行也放行）。
- 迁移：存量账号默认信任（旧布尔为真或无 profile ⇒ 造 manual approved 行）。
"""
from django.contrib.auth.models import AnonymousUser, User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory, TestCase, TransactionTestCase

from accounts.models import Verification, is_verified
from accounts.permissions import IsVerified


class IsVerifiedComputationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_anonymous_not_verified(self):
        self.assertFalse(is_verified(AnonymousUser()))

    def test_no_rows_not_verified(self):
        self.assertFalse(is_verified(self.user))

    def test_pending_only_not_verified(self):
        Verification.objects.create(
            user=self.user, channel=Verification.CHANNEL_EMAIL, status=Verification.STATUS_PENDING,
            identifier="u@e.com",
        )
        self.assertFalse(is_verified(self.user))

    def test_rejected_only_not_verified(self):
        Verification.objects.create(
            user=self.user, channel=Verification.CHANNEL_MANUAL, status=Verification.STATUS_REJECTED,
        )
        self.assertFalse(is_verified(self.user))

    def test_approved_email_verified(self):
        Verification.objects.create(
            user=self.user, channel=Verification.CHANNEL_EMAIL, status=Verification.STATUS_APPROVED,
            identifier="u@e.com",
        )
        self.assertTrue(is_verified(self.user))

    def test_approved_manual_verified(self):
        Verification.objects.create(
            user=self.user, channel=Verification.CHANNEL_MANUAL, status=Verification.STATUS_APPROVED,
        )
        self.assertTrue(is_verified(self.user))

    def test_any_approved_suffices(self):
        # 一个 rejected + 一个 approved ⇒ 已验证（any-of）
        Verification.objects.create(
            user=self.user, channel=Verification.CHANNEL_MANUAL, status=Verification.STATUS_REJECTED,
        )
        Verification.objects.create(
            user=self.user, channel=Verification.CHANNEL_EMAIL, status=Verification.STATUS_APPROVED,
            identifier="u@e.com",
        )
        self.assertTrue(is_verified(self.user))

    def test_is_verified_pure_no_superuser_special_case(self):
        # 纯计算不含逃生舱：超级用户无 approved 行 ⇒ 未验证（门禁 IsVerified 另行放行）
        self.user.is_superuser = True
        self.user.save()
        self.assertFalse(is_verified(self.user))


class IsVerifiedGateSuperuserBypassTest(TestCase):
    """超级用户是唯一应用访问逃生舱（ADR-0005 决策 9）：无 approved 行也放行写动作。"""

    def test_superuser_allowed_without_verification(self):
        u = User.objects.create_superuser(username="root", password="p")
        req = RequestFactory().post("/")
        req.user = u
        self.assertTrue(IsVerified().has_permission(req, None))

    def test_normal_user_blocked_without_verification(self):
        u = User.objects.create_user(username="u", password="p")
        req = RequestFactory().post("/")
        req.user = u
        self.assertFalse(IsVerified().has_permission(req, None))

    def test_verified_user_allowed(self):
        u = User.objects.create_user(username="u", password="p")
        Verification.objects.create(
            user=u, channel=Verification.CHANNEL_MANUAL, status=Verification.STATUS_APPROVED
        )
        req = RequestFactory().post("/")
        req.user = u
        self.assertTrue(IsVerified().has_permission(req, None))


class VerificationDefaultTrustMigrationTest(TransactionTestCase):
    """迁移 0004 默认信任：存量账号（旧布尔为真或无 profile）⇒ 造 manual approved 行。

    用 TransactionTestCase：迁移 DDL 在 SQLite 下须在外层事务之外执行（TestCase 把整测
    包进单事务，与 schema_editor 的 FK 检查开关冲突）。
    """

    migrate_from = [("accounts", "0003_profile_email_verified_profile_identity_and_more")]
    migrate_to = [("accounts", "0004_remove_profile_email_verified_and_more")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        executor.migrate(self.migrate_from)
        self._seed_pre_feature_users(old_apps)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        self.apps_after = executor.loader.project_state(self.migrate_to).apps

    def _seed_pre_feature_users(self, apps):
        User = apps.get_model("auth", "User")
        Profile = apps.get_model("accounts", "Profile")
        # 1) 有 profile、旧布尔默认为真（信任态）
        trusted = User.objects.create_user(username="legacy", password="p")
        Profile.objects.create(user=trusted)
        # 2) 无 profile（懒创建）——旧逻辑亦视为信任
        User.objects.create_user(username="noprofile", password="p")
        # 3) 显式未验证的自助注册账号（旧 register 曾设两布尔 False）——不应被信任
        unverified = User.objects.create_user(username="selfreg", password="p")
        Profile.objects.create(user=unverified, identity_verified=False, email_verified=False)

    def test_trusted_profile_user_becomes_verified(self):
        Verification = self.apps_after.get_model("accounts", "Verification")
        User = self.apps_after.get_model("auth", "User")
        u = User.objects.get(username="legacy")
        self.assertTrue(
            Verification.objects.filter(user=u, channel="manual", status="approved").exists()
        )

    def test_no_profile_user_becomes_verified(self):
        Verification = self.apps_after.get_model("accounts", "Verification")
        User = self.apps_after.get_model("auth", "User")
        u = User.objects.get(username="noprofile")
        self.assertTrue(
            Verification.objects.filter(user=u, channel="manual", status="approved").exists()
        )

    def test_explicitly_unverified_user_not_trusted(self):
        Verification = self.apps_after.get_model("accounts", "Verification")
        User = self.apps_after.get_model("auth", "User")
        u = User.objects.get(username="selfreg")
        self.assertFalse(Verification.objects.filter(user=u).exists())
