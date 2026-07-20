from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import News


def _info(user):
    g, _ = Group.objects.get_or_create(name="信息组")
    user.groups.add(g)
    return user


class NewsPermissionTest(TestCase):
    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.normal = User.objects.create_user(username="normal", password="x")
        self.client = APIClient()
        self.news = News.objects.create(title="t", author=self.author, is_published=True)

    def test_anon_can_read_list(self):
        self.assertEqual(self.client.get("/news/news/").status_code, 200)

    def test_info_group_can_create(self):
        self.client.force_authenticate(self.author)
        resp = self.client.post("/news/news/", {"title": "new"}, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_normal_user_cannot_create(self):
        self.client.force_authenticate(self.normal)
        resp = self.client.post("/news/news/", {"title": "new"}, format="json")
        self.assertEqual(resp.status_code, 403)


class NewsReaderCountTest(TestCase):
    """阅读量去重（登录按 user / 匿名按 IP）与头条（手工优先 else 最热）。"""

    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.normal = User.objects.create_user(username="normal", password="x")
        self.client = APIClient()
        self.news = News.objects.create(title="t", author=self.author, is_published=True)

    def test_view_once_per_user(self):
        """同一登录用户多次打开详情只算一次阅读。"""
        self.client.force_authenticate(self.normal)
        for _ in range(3):
            self.client.get(f"/news/news/{self.news.pk}/")
        self.news.refresh_from_db()
        self.assertEqual(self.news.views, 1)
        self.assertEqual(self.news.view_records.count(), 1)

    def test_view_once_per_ip_anon(self):
        """同一匿名 IP 多次打开详情只算一次阅读。"""
        for _ in range(3):
            self.client.get(f"/news/news/{self.news.pk}/")
        self.news.refresh_from_db()
        self.assertEqual(self.news.views, 1)

    def test_different_users_each_count(self):
        """不同登录用户各算一次阅读。"""
        other = User.objects.create_user(username="other", password="x")
        self.client.force_authenticate(self.normal)
        self.client.get(f"/news/news/{self.news.pk}/")
        self.client.force_authenticate(other)
        self.client.get(f"/news/news/{self.news.pk}/")
        self.news.refresh_from_db()
        self.assertEqual(self.news.views, 2)

    def test_featured_manual_priority(self):
        """手工置顶（featured）优先于阅读人数最高。"""
        News.objects.create(title="hot", author=self.author, is_published=True, views=100)
        feat = News.objects.create(
            title="feat", author=self.author, is_published=True, views=1, featured=True
        )
        resp = self.client.get("/news/news/featured/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], feat.id)

    def test_featured_fallback_hottest(self):
        """无手工置顶时头条取阅读人数最高的一条。"""
        News.objects.create(title="low", author=self.author, is_published=True, views=1)
        high = News.objects.create(title="high", author=self.author, is_published=True, views=100)
        resp = self.client.get("/news/news/featured/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], high.id)
