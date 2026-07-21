import json
from datetime import timedelta
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserSession
from .utils import get_client_ip, parse_user_agent, record_user_session


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="secret123",
        )

    def test_login_with_username_success(self):
        response = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "testuser", "password": "secret123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["username"], "testuser")
        self.assertEqual(data["user"]["email"], "test@example.com")

    def test_login_with_email_success(self):
        response = self.client.post(
            "/auth/login/",
            data=json.dumps({"email": "test@example.com", "password": "secret123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["username"], "testuser")

    def test_login_wrong_password(self):
        response = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "testuser", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_login_missing_fields(self):
        response = self.client.post(
            "/auth/login/",
            data=json.dumps({"username": "testuser"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class CsrfCookieViewTest(TestCase):
    """GET /auth/csrf/ 显式下发 csrftoken cookie。

    生产环境由 Django 渲染 dist/index.html（含 {% csrf_token %}）下发 cookie；
    但开发态 webpack 直接服务模板，{% csrf_token %} 只是字面文本、不会下发 cookie，
    导致全新访客 POST /auth/login/ 收到 403。此端点把 cookie 下发与 HTML 渲染解耦。
    """

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="secret123")

    def test_csrf_endpoint_sets_cookie(self):
        c = Client(enforce_csrf_checks=True)
        response = c.get("/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_login_after_csrf_prime_does_not_403(self):
        # enforce_csrf_checks=True 复现真实浏览器：无 csrftoken cookie 时 POST 会被 403
        c = Client(enforce_csrf_checks=True)
        c.get("/auth/csrf/")  # 显式下发 cookie
        token_cookie = c.cookies.get("csrftoken")
        token = token_cookie.value if token_cookie else ""
        response = c.post(
            "/auth/login/",
            data=json.dumps({"username": "testuser", "password": "secret123"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertNotEqual(response.status_code, 403)
        self.assertEqual(response.status_code, 200)


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="secret123")

    def test_logout_success(self):
        self.client.login(username="testuser", password="secret123")
        response = self.client.post("/auth/logout/")
        self.assertEqual(response.status_code, 200)

    def test_logout_unauthenticated(self):
        response = self.client.post("/auth/logout/")
        self.assertEqual(response.status_code, 302)

    def test_logout_clears_current_session_row(self):
        self.client.login(username="testuser", password="secret123")
        self.assertTrue(UserSession.objects.filter(user=self.user, is_current=True).exists())
        self.client.post("/auth/logout/")
        self.assertFalse(UserSession.objects.filter(user=self.user, is_current=True).exists())


class MeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="secret123",
        )

    def test_me_authenticated(self):
        self.client.login(username="testuser", password="secret123")
        response = self.client.get("/auth/me/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["username"], "testuser")

    def test_me_unauthenticated(self):
        response = self.client.get("/auth/me/")
        self.assertEqual(response.status_code, 302)

    def test_me_permissions_all_false_for_normal_user(self):
        self.client.login(username="testuser", password="secret123")
        perms = self.client.get("/auth/me/").json()["user"]["permissions"]
        self.assertFalse(any(perms.values()))

    def test_me_permissions_for_info_group(self):
        from django.contrib.auth.models import Group
        grp, _ = Group.objects.get_or_create(name="信息组")
        self.user.groups.add(grp)
        self.client.login(username="testuser", password="secret123")
        perms = self.client.get("/auth/me/").json()["user"]["permissions"]
        self.assertTrue(perms["can_manage_news"])
        self.assertFalse(perms["can_manage_tasks"])

    def test_me_permissions_for_president(self):
        from django.contrib.auth.models import Group
        grp, _ = Group.objects.get_or_create(name="社长")
        self.user.groups.add(grp)
        self.client.login(username="testuser", password="secret123")
        perms = self.client.get("/auth/me/").json()["user"]["permissions"]
        self.assertTrue(perms["can_manage_tasks"])
        self.assertTrue(perms["can_approve_proposals"])
        self.assertTrue(perms["can_change_proposals"])
        self.assertTrue(perms["can_view_feedback"])
        self.assertFalse(perms["can_manage_news"])


class PasswordResetViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="oldsecret123",
        )

    def test_password_reset_success(self):
        response = self.client.post(
            "/auth/password-reset/",
            data=json.dumps({"email": "test@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())

    def test_password_reset_unknown_email(self):
        response = self.client.post(
            "/auth/password-reset/",
            data=json.dumps({"email": "unknown@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())

    def test_password_reset_missing_email(self):
        response = self.client.post(
            "/auth/password-reset/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class PasswordResetConfirmViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="oldsecret123",
        )

    def _get_reset_token(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        return uid, token

    def test_password_reset_confirm_success(self):
        uid, token = self._get_reset_token()
        response = self.client.post(
            "/auth/password-reset/confirm/",
            data=json.dumps({
                "uid": uid,
                "token": token,
                "new_password": "newsecret456",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            self.client.login(username="testuser", password="newsecret456")
        )

    def test_password_reset_confirm_invalid_token(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.post(
            "/auth/password-reset/confirm/",
            data=json.dumps({
                "uid": uid,
                "token": "invalid-token",
                "new_password": "newsecret456",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_password_reset_confirm_missing_fields(self):
        response = self.client.post(
            "/auth/password-reset/confirm/",
            data=json.dumps({"uid": "MQ"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class UserSessionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_create_session_defaults(self):
        s = UserSession.objects.create(user=self.user, session_key="abc")
        self.assertTrue(s.is_current)
        self.assertEqual(s.device_type, "Unknown")
        self.assertEqual(s.device_name, "")

    def test_str_contains_username(self):
        s = UserSession.objects.create(user=self.user, session_key="abcdef0123456789")
        self.assertIn("u", str(s))


class ParseUserAgentTest(TestCase):
    def test_desktop_chrome_windows(self):
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        dtype, dname = parse_user_agent(ua)
        self.assertEqual(dtype, "Desktop")
        self.assertIn("Chrome", dname)
        self.assertIn("Windows", dname)

    def test_mobile_iphone(self):
        ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
              "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1")
        dtype, dname = parse_user_agent(ua)
        self.assertEqual(dtype, "Mobile")
        self.assertIn("iOS", dname)

    def test_tablet_ipad(self):
        ua = ("Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
        dtype, _ = parse_user_agent(ua)
        self.assertEqual(dtype, "Tablet")

    def test_bot(self):
        dtype, _ = parse_user_agent("Mozilla/5.0 (compatible; Googlebot/2.1; +http://google.com/bot.html)")
        self.assertEqual(dtype, "Bot")

    def test_empty(self):
        self.assertEqual(parse_user_agent(""), ("Unknown", ""))


class GetClientIpTest(TestCase):
    def test_remote_addr(self):
        req = RequestFactory().get("/", REMOTE_ADDR="1.2.3.4")
        self.assertEqual(get_client_ip(req), "1.2.3.4")


class RecordUserSessionTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="u", password="p")

    def _req(self):
        return self.factory.get(
            "/",
            REMOTE_ADDR="9.9.9.9",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0",
        )

    def test_creates_current_row(self):
        record_user_session(self._req(), self.user, "keyA")
        s = UserSession.objects.get(session_key="keyA")
        self.assertTrue(s.is_current)
        self.assertEqual(s.ip_address, "9.9.9.9")
        self.assertEqual(s.device_type, "Desktop")

    def test_second_login_supersedes_first(self):
        record_user_session(self._req(), self.user, "keyA")
        record_user_session(self._req(), self.user, "keyB")
        # 历史保留：两行都在；is_current 仅 keyB
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 2)
        current = UserSession.objects.get(user=self.user, is_current=True)
        self.assertEqual(current.session_key, "keyB")

    def test_same_key_updates_in_place(self):
        record_user_session(self._req(), self.user, "keyA")
        record_user_session(self._req(), self.user, "keyA")
        self.assertEqual(UserSession.objects.filter(session_key="keyA").count(), 1)
        self.assertTrue(UserSession.objects.get(session_key="keyA").is_current)

    def test_history_pruned_to_limit(self):
        # 制造 25 次登录：保留最近 20 条，最旧的被裁掉
        for i in range(25):
            record_user_session(self._req(), self.user, f"key{i:02d}")
        rows = list(UserSession.objects.filter(user=self.user).order_by("created_at", "id"))
        self.assertEqual(len(rows), 20, "应精确裁剪到 20 条")  # 改为精确断言确保失败
        # 当前会话（最后一次 key24）必在保留之列且为 current
        current = UserSession.objects.get(user=self.user, is_current=True)
        self.assertEqual(current.session_key, "key24")
        self.assertIn(current.id, [r.id for r in rows])


class LoginSignalIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@e.com", password="secret123")

    def test_login_creates_user_session(self):
        c = Client()
        c.login(username="u", password="secret123")
        s = UserSession.objects.get(user=self.user)
        self.assertTrue(s.is_current)
        self.assertTrue(s.session_key)

    def test_login_records_device_info(self):
        c = Client()
        c.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "secret123"}),
            content_type="application/json",
            REMOTE_ADDR="1.2.3.4",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0",
        )
        s = UserSession.objects.get(user=self.user)
        self.assertEqual(s.ip_address, "1.2.3.4")
        self.assertEqual(s.device_type, "Desktop")
        self.assertIn("Chrome", s.device_name)

    def test_second_device_login_leaves_single_current_row(self):
        a = Client()
        a.login(username="u", password="secret123")
        b = Client()
        b.login(username="u", password="secret123")
        self.assertEqual(UserSession.objects.filter(user=self.user, is_current=True).count(), 1)


class SingleSessionMiddlewareTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@e.com", password="secret123")

    def _login(self):
        c = Client()
        c.login(username="u", password="secret123")
        return c

    def test_first_device_can_access(self):
        a = self._login()
        self.assertEqual(a.get("/auth/me/").status_code, 200)

    def test_superseded_device_gets_401_with_takeover(self):
        a = self._login()
        # 老化 a 的当前会话到保护期外（≥10 分钟），b 才能挤号
        UserSession.objects.filter(user=self.user, is_current=True).update(
            created_at=timezone.now() - timedelta(minutes=11)
        )
        b = Client()
        b.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "secret123"}),
            content_type="application/json",
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148 Safari",
        )
        resp = a.get("/auth/me/")
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertEqual(data["reason"], "session_superseded")
        self.assertEqual(data["takeover"]["device_type"], "Mobile")
        self.assertIn("iOS", data["takeover"]["device_name"])
        self.assertIn("time", data["takeover"])

    def test_new_device_can_access_after_takeover(self):
        a = self._login()
        b = self._login()
        self.assertEqual(b.get("/auth/me/").status_code, 200)

    def test_anonymous_request_passes_through(self):
        # /auth/me/ is login_required → anonymous gets 302, not a 500 from the middleware
        self.assertEqual(Client().get("/auth/me/").status_code, 302)

    def test_pre_feature_session_is_adopted(self):
        a = self._login()
        UserSession.objects.all().delete()  # simulate a session that predates this feature
        self.assertEqual(a.get("/auth/me/").status_code, 200)
        self.assertTrue(UserSession.objects.filter(user=self.user, is_current=True).exists())


class CrossUserReloginTest(TestCase):
    def test_second_user_login_on_same_session_records_row(self):
        # Same Client (same cookie jar) simulates one browser where user A didn't log out
        # before user B signs in. Django's login() takes the flush() branch here.
        User.objects.create_user(username="aaa", password="secret123")
        User.objects.create_user(username="bbb", password="secret123")
        c = Client()
        c.login(username="aaa", password="secret123")
        # Now sign in as bbb on the SAME client (no logout in between):
        c.login(username="bbb", password="secret123")
        bbb = User.objects.get(username="bbb")
        # B must have a current UserSession row:
        self.assertTrue(
            UserSession.objects.filter(user=bbb, is_current=True).exists(),
            "second-user login on a shared session did not record a UserSession row",
        )
        # And B must be able to access an authenticated view (not kicked):
        self.assertEqual(c.get("/auth/me/").status_code, 200)


class LoginProtectionTest(TestCase):
    """10 分钟登录保护：登录后 10 分钟内，他方新会话登录该账号被拒绝。"""
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@e.com", password="secret123")

    def _post_login(self, client, **extra):
        return client.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "secret123"}),
            content_type="application/json",
            **extra,
        )

    def test_second_login_within_window_is_blocked(self):
        a = Client()
        a.login(username="u", password="secret123")  # 建立当前会话（age≈0）
        b = Client()
        resp = self._post_login(b)
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data["reason"], "login_protection")
        self.assertGreater(data["retry_after"], 0)
        # a 仍是当前会话、可继续访问
        self.assertEqual(UserSession.objects.filter(user=self.user, is_current=True).count(), 1)
        self.assertEqual(a.get("/auth/me/").status_code, 200)

    def test_second_login_after_window_is_allowed(self):
        a = Client()
        a.login(username="u", password="secret123")
        UserSession.objects.filter(user=self.user, is_current=True).update(
            created_at=timezone.now() - timedelta(minutes=11)
        )
        b = Client()
        resp = self._post_login(b)
        self.assertEqual(resp.status_code, 200)
        # a 现已被挤下线
        self.assertEqual(a.get("/auth/me/").status_code, 401)

    def test_logout_releases_protection(self):
        a = Client()
        a.login(username="u", password="secret123")
        a.post("/auth/logout/")  # 主动登出 → 清 is_current（依赖 Task 2）
        b = Client()
        resp = self._post_login(b)
        self.assertEqual(resp.status_code, 200)

    def test_same_session_reauth_is_exempt(self):
        c = Client()
        c.login(username="u", password="secret123")  # 当前会话 = c 的 session_key
        # 同一 client（同一 session_key）再次提交登录 → 不拦截
        resp = self._post_login(c)
        self.assertEqual(resp.status_code, 200)

    def test_wrong_password_not_treated_as_protection(self):
        a = Client()
        a.login(username="u", password="secret123")
        b = Client()
        resp = b.post(
            "/auth/login/",
            data=json.dumps({"username": "u", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertNotEqual(resp.json().get("reason"), "login_protection")


class SessionsViewTest(TestCase):
    """GET /auth/sessions/：返回本人最近 20 条登录记录（按时间倒序，含 is_current）。"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="secret123",
        )

    def _login(self):
        c = Client()
        c.post(
            "/auth/login/",
            data=json.dumps({"username": "testuser", "password": "secret123"}),
            content_type="application/json",
            REMOTE_ADDR="5.6.7.8",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0",
        )
        return c

    def test_requires_login(self):
        resp = Client().get("/auth/sessions/")
        self.assertEqual(resp.status_code, 302)

    def test_response_shape_and_device_info(self):
        c = self._login()
        row = c.get("/auth/sessions/").json()["results"][0]
        for key in ("id", "device_name", "device_type", "ip_address", "created_at", "is_current"):
            self.assertIn(key, row)
        self.assertEqual(row["ip_address"], "5.6.7.8")
        self.assertEqual(row["device_type"], "Desktop")
        self.assertIn("Chrome", row["device_name"])
        self.assertTrue(row["is_current"])

    def test_ordered_desc_current_first(self):
        c = self._login()  # 当前会话：最新
        base = timezone.now() - timedelta(hours=2)
        # 先创建再 update created_at（auto_now_add 会覆盖 create 时的显式值）
        h1 = UserSession.objects.create(user=self.user, session_key="h1", is_current=False)
        h2 = UserSession.objects.create(user=self.user, session_key="h2", is_current=False)
        UserSession.objects.filter(pk=h1.pk).update(created_at=base)
        UserSession.objects.filter(pk=h2.pk).update(created_at=base + timedelta(minutes=30))
        results = c.get("/auth/sessions/").json()["results"]
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]["is_current"])  # 最新（当前会话）排第一
        times = [r["created_at"] for r in results]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_returns_only_own_sessions(self):
        other = User.objects.create_user(username="other", password="secret123")
        oc = Client()
        oc.login(username="other", password="secret123")  # 产生 other 的记录
        c = self._login()
        results = c.get("/auth/sessions/").json()["results"]
        expected = UserSession.objects.filter(user=self.user).count()
        self.assertEqual(len(results), expected)  # 只返回本人，不含 other

    def test_caps_at_history_limit(self):
        c = self._login()  # 1 条当前会话
        base = timezone.now() - timedelta(hours=1)
        # 直接造 21 条更早的历史（不经 record_user_session，不触发裁剪）
        for i in range(21):
            UserSession.objects.create(
                user=self.user,
                session_key=f"extra{i:02d}",
                is_current=False,
                created_at=base + timedelta(seconds=i),
            )
        results = c.get("/auth/sessions/").json()["results"]
        self.assertEqual(len(results), 20)  # 视图裁剪到 SESSION_HISTORY_LIMIT
