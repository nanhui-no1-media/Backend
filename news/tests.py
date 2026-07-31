from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase, RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from proposals.models import Proposal
from tasks.models import Task

from .models import News
from .feed import build_feed


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


class NewsOverviewTest(TestCase):
    """社团概览：成员=活跃用户数，作品=已发布新闻数；匿名可读。"""

    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.normal = User.objects.create_user(username="normal", password="x")
        News.objects.create(title="published", author=self.author, is_published=True)
        News.objects.create(title="draft", author=self.author, is_published=False)
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
        return News.objects.create(title=title, **kw)

    def _activity(self, title, days_ago=0, **kw):
        kw.setdefault("proposal_type", "activity")
        kw.setdefault("status", "approved")
        kw.setdefault("activity_type", "training")
        p = Proposal.objects.create(title=title, **kw)
        Proposal.objects.filter(pk=p.pk).update(approved_at=self._ts(days_ago))  # auto_now/add 之外的字段
        return p

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
        self._activity("act", days_ago=0, budget="1234.56", contact="secret", reject_reason="nope")
        act = next(i for i in build_feed(request=self.anon)["items"] if i["type"] == "activity")
        for forbidden in ("budget", "vote_summary", "reject_reason", "contact", "creator", "description"):
            self.assertNotIn(forbidden, act)
        self.assertEqual(act["activity_type"], "training")
        self.assertIn("phase", act)

    def test_limit_truncates(self):
        for i in range(10):
            self._news(f"n{i}", days_ago=i)
        data = build_feed(request=self.anon, limit=4)
        self.assertLessEqual(len(data["items"]), 4)

    def test_empty_when_no_content(self):
        data = build_feed(request=self.anon)
        self.assertIsNone(data["featured"])
        self.assertEqual(data["items"], [])

    def test_activity_phase_derived_from_planned_date(self):
        today = timezone.localdate()
        up = self._activity("up"); Proposal.objects.filter(pk=up.pk).update(planned_date=today + timedelta(days=2))
        og = self._activity("og"); Proposal.objects.filter(pk=og.pk).update(planned_date=today)
        ed = self._activity("ed"); Proposal.objects.filter(pk=ed.pk).update(planned_date=today - timedelta(days=2))
        by_title = {i["title"]: i["phase"]
                    for i in build_feed(request=self.anon)["items"] if i["type"] == "activity"}
        self.assertEqual(by_title["up"], "upcoming")
        self.assertEqual(by_title["og"], "ongoing")
        self.assertEqual(by_title["ed"], "ended")


class FeedEndpointTest(TestCase):
    """端点 /news/news/feed/：匿名可读、不含任务；登录含任务。"""

    def setUp(self):
        self.author = _info(User.objects.create_user(username="info", password="x"))
        self.member = User.objects.create_user(username="member", password="x")
        News.objects.create(title="n1", author=self.author, is_published=True)
        Proposal.objects.create(
            proposal_type="activity", status="approved",
            title="a1", activity_type="training",
        )
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
