"""Django admin review change form embeds the target SPA page."""
from django.contrib.auth.models import User
from django.test import Client, TestCase

from news.models import News
from reviews.lifecycle import open_review
from reviews.models import Review


class ReviewAdminPreviewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "a@e.com", "x")
        self.author = User.objects.create_user("author", password="x")
        self.news = News.objects.create(title="后台预览稿", content="<p>正文</p>", author=self.author)
        self.review = open_review(news=self.news, actor=self.author)

    def test_spa_allows_same_origin_framing(self):
        resp = Client().get("/")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_change_form_iframes_news_page(self):
        c = Client()
        c.force_login(self.admin)
        resp = c.get(f"/admin/reviews/review/{self.review.pk}/change/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("<iframe", body)
        self.assertIn(f"/#/news/{self.news.pk}?embed=1", body)
        self.assertIn("reviews/admin_preview.css", body)

    def test_change_form_iframes_activity_page(self):
        from datetime import timedelta
        from django.utils import timezone
        from activities.models import Activity

        act = Activity.objects.create(
            type="deliberation",
            status="open",
            title="后台活动预览",
            creator=self.author,
            end_at=timezone.now() + timedelta(days=1),
        )
        review = open_review(activity=act, actor=self.author)
        c = Client()
        c.force_login(self.admin)
        resp = c.get(f"/admin/reviews/review/{review.pk}/change/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(f"/#/activity/{act.pk}?embed=1", resp.content.decode())
