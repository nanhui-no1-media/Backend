from django.contrib.auth.models import Group, Permission, User
from django.db.models import Q
from django.test import TestCase

from reviews.visibility import public_q

from .visibility import (
    ContentVisibility,
    ProfileVisibility,
    content_visibility,
    is_admin_viewer,
    profile_view_for,
)


def _grant(user, app_label, codename):
    """直接授予某权限（不经组），并刷新实例以清权限缓存。"""
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label=app_label, codename=codename)
    )
    return User.objects.get(pk=user.pk)


# ---- 管理员判定：权限而非硬编码「信息组」组名（#8 故事 7-8）----


class IsAdminViewerTest(TestCase):
    def setUp(self):
        self.regular = User.objects.create_user(username="regular", password="p")
        # 直接授予权限（不在「信息组」组里）—— 钉死「权限即管理员」
        self.direct = _grant(User.objects.create_user(username="direct", password="p"), "news", "add_news")
        # 经「信息组」组获得权限（组仍生效，因其授予该权限）
        info = User.objects.create_user(username="info", password="p")
        info.groups.add(Group.objects.get_or_create(name="信息组")[0])
        self.in_info_group = User.objects.get(pk=info.pk)
        # 在某组但该组不授 news.add_news —— 钉死「组名本身不算数」
        other = User.objects.create_user(username="other_grp", password="p")
        other.groups.add(Group.objects.create(name="noop_group"))
        self.in_other_group = User.objects.get(pk=other.pk)
        self.superuser = User.objects.create_superuser(username="root", email="r@e.com", password="p")

    def test_superuser_is_admin(self):
        self.assertTrue(is_admin_viewer(self.superuser))

    def test_direct_permission_is_admin(self):
        # 授予 news.add_news（不在信息组）→ 仍是管理员
        self.assertTrue(is_admin_viewer(self.direct))

    def test_info_group_member_is_admin(self):
        # 信息组成员（经组获得 news.add_news）→ 管理员
        self.assertTrue(is_admin_viewer(self.in_info_group))

    def test_regular_is_not_admin(self):
        self.assertFalse(is_admin_viewer(self.regular))

    def test_group_without_permission_is_not_admin(self):
        # 关键钉死：仅在某组（无 news.add_news）不算管理员
        self.assertFalse(is_admin_viewer(self.in_other_group))


# ---- 资料字段可见性矩阵（#8 故事 1-6）----


class ProfileViewForTest(TestCase):
    def setUp(self):
        self.viewed = User.objects.create_user(username="viewed", email="v@e.com", password="p")
        self.other = User.objects.create_user(username="other", password="p")
        self.admin = _grant(
            User.objects.create_user(username="admin", password="p"), "news", "add_news"
        )
        self.inactive = User.objects.create_user(username="inactive", password="p", is_active=False)

    def test_owner_sees_private_and_sensitive(self):
        v = profile_view_for(self.viewed, self.viewed)
        self.assertIsInstance(v, ProfileVisibility)
        self.assertTrue(v.is_owner)
        self.assertFalse(v.is_admin)
        self.assertTrue(v.can_see_private)     # email / birthday / gender
        self.assertTrue(v.can_see_sensitive)   # permissions / groups

    def test_admin_sees_sensitive_but_not_private(self):
        v = profile_view_for(self.admin, self.viewed)
        self.assertFalse(v.is_owner)
        self.assertTrue(v.is_admin)
        self.assertFalse(v.can_see_private)
        self.assertTrue(v.can_see_sensitive)

    def test_regular_other_sees_neither(self):
        v = profile_view_for(self.other, self.viewed)
        self.assertFalse(v.is_owner)
        self.assertFalse(v.is_admin)
        self.assertFalse(v.can_see_private)
        self.assertFalse(v.can_see_sensitive)

    def test_module_is_inactive_agnostic(self):
        # 模块不按 is_active 裁剪（停用→404 的边界在视图层）；裁定与正常用户一致。
        v = profile_view_for(self.other, self.inactive)
        self.assertFalse(v.is_owner)
        self.assertFalse(v.can_see_private)


# ---- 内容可见性矩阵（#8 故事 9-14）----


class ContentVisibilityTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="p")
        self.other = User.objects.create_user(username="other", password="p")

    def test_news_owner_sees_all(self):
        self.assertEqual(
            content_visibility(self.owner, self.owner, "news"),
            ContentVisibility(denied=False, extra_q=Q()),
        )

    def test_news_other_only_published(self):
        vis = content_visibility(self.other, self.owner, "news")
        self.assertEqual(
            vis,
            ContentVisibility(denied=False, extra_q=public_q("news") & Q(is_published=True)),
        )

    def test_proposals_owner_sees_all(self):
        self.assertEqual(
            content_visibility(self.owner, self.owner, "proposals"),
            ContentVisibility(denied=False, extra_q=Q()),
        )

    def test_proposals_other_only_approved(self):
        self.assertEqual(
            content_visibility(self.other, self.owner, "proposals"),
            ContentVisibility(denied=False, extra_q=Q(status="approved")),
        )

    def test_tasks_owner_ok(self):
        self.assertEqual(
            content_visibility(self.owner, self.owner, "tasks"),
            ContentVisibility(denied=False, extra_q=Q()),
        )

    def test_tasks_other_denied(self):
        # 任务仅本人；他人无权（视图据此 403）
        self.assertEqual(
            content_visibility(self.other, self.owner, "tasks"),
            ContentVisibility(denied=True, extra_q=Q()),
        )

    def test_activities_owner_sees_all(self):
        self.assertEqual(
            content_visibility(self.owner, self.owner, "activities"),
            ContentVisibility(denied=False, extra_q=Q()),
        )

    def test_activities_other_extra_q_matches_public_q(self):
        vis = content_visibility(self.other, self.owner, "activities")
        self.assertFalse(vis.denied)
        self.assertEqual(vis.extra_q, public_q("activity"))

    def test_tutorials_owner_sees_all(self):
        self.assertEqual(
            content_visibility(self.owner, self.owner, "tutorials"),
            ContentVisibility(denied=False, extra_q=Q()),
        )

    def test_tutorials_other_extra_q_matches_public_q(self):
        vis = content_visibility(self.other, self.owner, "tutorials")
        self.assertFalse(vis.denied)
        self.assertEqual(vis.extra_q, public_q("tutorial"))

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            content_visibility(self.other, self.owner, "bogus")
