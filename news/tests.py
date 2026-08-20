from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase, RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from proposals.models import Proposal
from activities.models import Activity
from tasks.models import Task

from reviews.test_helpers import approve_news
from .models import News
from .feed import build_feed


def _info(user):
    g, _ = Group.objects.get_or_create(name="信息组")
    user.groups.add(g)
    return user


class NewsContentSanitizeTest(TestCase):
    """NewsDetailSerializer.validate_content 仍经 sanitize_html（与 common 共享净化）。"""

    def test_validate_content_strips_script(self):
        from news.serializers import NewsDetailSerializer
        out = NewsDetailSerializer().validate_content("<p>ok</p><script>alert(1)</script>")
        self.assertNotIn("<script", out)
        self.assertIn("ok", out)


class NewsPermissionTest(TestCase):
    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.normal = User.objects.create_user(username="normal", password="x")
        self.client = APIClient()
        self.news = approve_news(News.objects.create(title="t", author=self.author, is_published=True))

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
        self.news = approve_news(News.objects.create(title="t", author=self.author, is_published=True))

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
        approve_news(News.objects.create(title="hot", author=self.author, is_published=True, views=100))
        feat = approve_news(News.objects.create(
            title="feat", author=self.author, is_published=True, views=1, featured=True
        ))
        resp = self.client.get("/news/news/featured/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], feat.id)

    def test_featured_fallback_hottest(self):
        """无手工置顶时头条取阅读人数最高的一条。"""
        approve_news(News.objects.create(title="low", author=self.author, is_published=True, views=1))
        high = approve_news(News.objects.create(title="high", author=self.author, is_published=True, views=100))
        resp = self.client.get("/news/news/featured/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], high.id)


class NewsOverviewTest(TestCase):
    """社团概览：成员=活跃用户数，作品=已发布新闻数；匿名可读。"""

    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.normal = User.objects.create_user(username="normal", password="x")
        News.objects.create(title="published", author=self.author, is_published=True)
        News.objects.create(title="draft", author=self.author, is_published=False)
        approve_news(News.objects.get(title="published"))
        self.client = APIClient()

    def test_anon_overview_counts(self):
        """匿名可读；成员=活跃用户数，作品=已发布新闻数（草稿不计）。"""
        resp = self.client.get("/news/news/overview/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["members"], 2)  # author + normal，均活跃
        self.assertEqual(resp.data["works"], 1)    # 仅 1 条已发布

    def test_inactive_users_not_counted(self):
        """停用账号不计入成员数。"""
        User.objects.create_user(username="ghost", password="x", is_active=False)
        resp = self.client.get("/news/news/overview/")
        self.assertEqual(resp.data["members"], 2)


class FeedTest(TestCase):
    """build_feed：可见性 / 排序 / 打散 / 公开投影 / limit / 空态。"""

    def setUp(self):
        self.rf = RequestFactory()
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.member = User.objects.create_user(username="member", password="x")
        self.anon = self.rf.get("/news/news/feed/")
        self.anon.user = AnonymousUser()
        self.authed = self.rf.get("/news/news/feed/")
        self.authed.user = self.member

    # ---- fixtures ----
    @staticmethod
    def _ts(days_ago):
        return timezone.now() - timedelta(days=days_ago)

    def _news(self, title, days_ago=0, **kw):
        kw.setdefault("author", self.author)
        kw.setdefault("is_published", True)
        kw["published_at"] = self._ts(days_ago)
        return approve_news(News.objects.create(title=title, **kw))

    def _activity(self, title, days_ago=0, **kw):
        # 活动已迁移至 activities app（ADR 0007）；feed 取 created_at 作时间戳。
        kw.setdefault("type", "deliberation")
        kw.setdefault("status", "open")
        kw.setdefault("creator", self.author)
        a = Activity.objects.create(title=title, **kw)
        Activity.objects.filter(pk=a.pk).update(created_at=self._ts(days_ago))  # auto_now_add 之外需 .update
        return a

    def _task(self, title, days_ago=0, **kw):
        kw.setdefault("creator", self.member)
        kw.setdefault("status", "in_progress")
        t = Task.objects.create(title=title, **kw)
        Task.objects.filter(pk=t.pk).update(updated_at=self._ts(days_ago))  # auto_now 字段需 .update 绕过
        return t

    @staticmethod
    def _types(items):
        return [i["type"] for i in items]

    # ---- cases ----
    def test_featured_excluded_from_items(self):
        feat = self._news("feat", days_ago=1, featured=True)
        other = self._news("other", days_ago=0)
        data = build_feed(request=self.anon)
        self.assertEqual(data["featured"]["id"], feat.pk)
        ids = [i["id"] for i in data["items"]]
        self.assertIn(other.pk, ids)
        self.assertNotIn(feat.pk, ids)

    def test_anon_has_news_but_no_tasks(self):
        self._news("n1", days_ago=1)
        self._news("n2", days_ago=0)
        self._task("t", days_ago=0)
        data = build_feed(request=self.anon)
        self.assertNotIn("task", self._types(data["items"]))
        self.assertIn("news", self._types(data["items"]))

    def test_authed_includes_tasks(self):
        self._news("n1", days_ago=1)
        self._news("n2", days_ago=0)
        self._task("t", days_ago=0)
        data = build_feed(request=self.authed)
        self.assertIn("task", self._types(data["items"]))

    def test_ordering_desc_by_timestamp(self):
        self._news("feat", days_ago=10, featured=True)  # 头条，不参与 items
        self._news("old", days_ago=3)
        self._news("mid", days_ago=2)
        self._news("new", days_ago=1)
        data = build_feed(request=self.anon)
        self.assertEqual([i["title"] for i in data["items"]], ["new", "mid", "old"])

    def test_diversify_breaks_three_in_a_row(self):
        self._news("feat", days_ago=10, featured=True)  # 头条锚点，不参与 items（否则最热新闻会被选走，打散无从验证）
        self._activity("act", days_ago=4)                # 最旧
        self._news("old", days_ago=3)
        self._news("mid", days_ago=2)
        self._news("new", days_ago=1)                    # 排序后 [new,mid,old,act] → 连续 3 新闻需打散
        types = self._types(build_feed(request=self.anon)["items"])
        windows = [types[i:i + 3] for i in range(len(types) - 2)]
        self.assertNotIn(["news", "news", "news"], windows)
        self.assertEqual(set(types), {"news", "activity"})

    def test_activity_projection_excludes_internal_fields(self):
        self._activity("act", days_ago=0)
        act = next(i for i in build_feed(request=self.anon)["items"] if i["type"] == "activity")
        for forbidden in ("budget", "vote_summary", "reject_reason", "contact", "creator", "description", "body", "options"):
            self.assertNotIn(forbidden, act)
        self.assertIn(act["activity_type"], ("deliberation", "collection", "exhibition"))
        self.assertIn("status", act)

    def test_exhibition_activity_in_feed(self):
        """展示活动须进入 feed 且 activity_type=exhibition——前端 ActivityCard 据此查
        ACTIVITY_META 渲染；后端若漏投或类型串错，卡片即崩（回归 #49）。"""
        self._activity("影展", days_ago=0, type="exhibition", status="open")
        items = build_feed(request=self.anon)["items"]
        ex = next(
            (i for i in items if i["type"] == "activity" and i["activity_type"] == "exhibition"),
            None,
        )
        self.assertIsNotNone(ex, "展示活动应出现在 feed items 中")
        # 公开投影与其它活动同形：不泄露内部字段（展品/正文/选项等）
        for forbidden in ("budget", "body", "options", "exhibits", "creator"):
            self.assertNotIn(forbidden, ex)

    def test_limit_truncates(self):
        for i in range(10):
            self._news(f"n{i}", days_ago=i)
        data = build_feed(request=self.anon, limit=4)
        self.assertLessEqual(len(data["items"]), 4)

    def test_empty_when_no_content(self):
        data = build_feed(request=self.anon)
        self.assertIsNone(data["featured"])
        self.assertEqual(data["items"], [])


class FeedEndpointTest(TestCase):
    """端点 /news/news/feed/：匿名可读、不含任务；登录含任务。"""

    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.member = User.objects.create_user(username="member", password="x")
        approve_news(News.objects.create(title="n1", author=self.author, is_published=True))
        Activity.objects.create(type="deliberation", status="open", title="a1", creator=self.author)
        Task.objects.create(title="t1", creator=self.member, status="in_progress")
        self.client = APIClient()

    def test_anon_ok_without_tasks(self):
        resp = self.client.get("/news/news/feed/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("featured", resp.data)
        self.assertNotIn("task", {i["type"] for i in resp.data["items"]})

    def test_authed_includes_tasks(self):
        self.client.force_authenticate(self.member)
        resp = self.client.get("/news/news/feed/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("task", {i["type"] for i in resp.data["items"]})

    def test_limit_query_param(self):
        self.client.force_authenticate(self.member)
        resp = self.client.get("/news/news/feed/?limit=1")
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.data["items"]), 1)
