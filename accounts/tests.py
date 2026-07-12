import json
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
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

    def test_me_is_president_false_for_normal_user(self):
        self.client.login(username="testuser", password="secret123")
        data = self.client.get("/auth/me/").json()
        self.assertIn("is_president", data["user"])
        self.assertIs(data["user"]["is_president"], False)

    def test_me_is_president_true_for_president(self):
        from django.contrib.auth.models import Group
        grp, _ = Group.objects.get_or_create(name="社长")
        self.user.groups.add(grp)
        self.client.login(username="testuser", password="secret123")
        data = self.client.get("/auth/me/").json()
        self.assertIs(data["user"]["is_president"], True)


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
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)
        current = UserSession.objects.get(user=self.user)
        self.assertEqual(current.session_key, "keyB")
        self.assertTrue(current.is_current)

    def test_same_key_updates_in_place(self):
        record_user_session(self._req(), self.user, "keyA")
        record_user_session(self._req(), self.user, "keyA")
        self.assertEqual(UserSession.objects.filter(session_key="keyA").count(), 1)
        self.assertTrue(UserSession.objects.get(session_key="keyA").is_current)


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
