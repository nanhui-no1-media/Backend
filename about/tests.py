from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from about.models import AboutPage


def _change_perm():
    return Permission.objects.get(codename="change_aboutpage")


class AboutReadTest(TestCase):
    """GET /about/：公开可读（匿名 + 登录用户），返回单例内容。"""

    def setUp(self):
        self.client = APIClient()

    def test_anon_get_returns_singleton(self):
        resp = self.client.get("/about/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["title"], "关于我们")
        self.assertIn("content", resp.data)
        self.assertIn("updated_at", resp.data)

    def test_authed_without_perm_can_read(self):
        """登录但无 change 权限的用户也能读（关于页对所有人公开）。"""
        u = User.objects.create_user(username="u", password="x")
        self.client.force_authenticate(u)
        self.assertEqual(self.client.get("/about/").status_code, 200)


class AboutWriteTest(TestCase):
    """PUT /about/：仅持 about.change_aboutpage 者可改，保存即发布。"""

    def setUp(self):
        self.client = APIClient()
        self.editor = User.objects.create_user(username="editor", password="x")
        self.editor.user_permissions.add(_change_perm())
        self.normal = User.objects.create_user(username="normal", password="x")

    def test_anon_put_denied(self):
        resp = self.client.put("/about/", {"title": "x", "content": "y"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_normal_put_forbidden(self):
        self.client.force_authenticate(self.normal)
        resp = self.client.put("/about/", {"title": "x", "content": "y"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_editor_can_update(self):
        self.client.force_authenticate(self.editor)
        resp = self.client.put(
            "/about/", {"title": "新标题", "content": "<p>正文</p>"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        solo = AboutPage.objects.get_solo()
        self.assertEqual(solo.title, "新标题")
        self.assertEqual(solo.content, "<p>正文</p>")

    def test_editor_content_sanitized(self):
        """PUT 的正文经 sanitize_html：script 标签被剥离，正文保留。"""
        self.client.force_authenticate(self.editor)
        self.client.put(
            "/about/", {"content": "<p>ok</p><script>alert(1)</script>"}, format="json",
        )
        solo = AboutPage.objects.get_solo()
        self.assertNotIn("<script", solo.content)
        self.assertIn("ok", solo.content)


class AboutCapabilityTest(TestCase):
    """/auth/me/ 透出 can_edit_about（由 has_perm 派生）。"""

    def test_capability_reflects_perm(self):
        from accounts.views import _capabilities

        holder = User.objects.create_user(username="h", password="x")
        holder.user_permissions.add(_change_perm())
        self.assertTrue(_capabilities(holder)["can_edit_about"])

        nope = User.objects.create_user(username="n", password="x")
        self.assertFalse(_capabilities(nope)["can_edit_about"])

    def test_me_exposes_can_edit_about(self):
        holder = User.objects.create_user(username="h", password="x")
        holder.user_permissions.add(_change_perm())
        c = APIClient()
        # me_view 是 @login_required 的普通 Django 视图，用 login 而非 force_authenticate
        c.login(username="h", password="x")
        resp = c.get("/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["user"]["permissions"]["can_edit_about"])


class AboutSingletonTest(TestCase):
    """AboutPage 为单例：全局仅一行（pk 恒为 1），且始终存在。"""

    def test_only_one_row(self):
        """save() 强制 pk=1：二次 create 等价于更新，不会产生第二行。"""
        AboutPage.objects.create(title="a")
        AboutPage.objects.create(title="b")
        self.assertEqual(AboutPage.objects.count(), 1)
        self.assertEqual(AboutPage.objects.get().title, "b")

    def test_get_solo_always_returns_pk1(self):
        solo = AboutPage.objects.get_solo()
        self.assertEqual(solo.pk, 1)
        self.assertEqual(solo.title, "关于我们")
