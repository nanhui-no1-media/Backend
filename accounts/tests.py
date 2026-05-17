import json
from django.test import TestCase, Client
from django.contrib.auth.models import User


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
            "/api/auth/login/",
            data=json.dumps({"username": "testuser", "password": "secret123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["username"], "testuser")
        self.assertEqual(data["user"]["email"], "test@example.com")

    def test_login_with_email_success(self):
        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"email": "test@example.com", "password": "secret123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["username"], "testuser")

    def test_login_wrong_password(self):
        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "testuser", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_login_missing_fields(self):
        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "testuser"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_success(self):
        response = self.client.post(
            "/api/auth/register/",
            data=json.dumps({
                "username": "newuser",
                "email": "new@example.com",
                "password": "secret123",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["user"]["username"], "newuser")
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_duplicate_username(self):
        User.objects.create_user(username="existing", password="secret123")
        response = self.client.post(
            "/api/auth/register/",
            data=json.dumps({
                "username": "existing",
                "email": "other@example.com",
                "password": "secret123",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_register_missing_fields(self):
        response = self.client.post(
            "/api/auth/register/",
            data=json.dumps({"username": "newuser"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="secret123")

    def test_logout_success(self):
        self.client.login(username="testuser", password="secret123")
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 200)

    def test_logout_unauthenticated(self):
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 401)


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
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["username"], "testuser")

    def test_me_unauthenticated(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
