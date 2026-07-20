# 首页「社团动态」聚合 Feed 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用真实数据替换首页 `HomePage.tsx` 的 mock「社团动态」，聚合 活动 / 任务 / 新闻 三类内容，按「头条 + 便当格」多样呈现。

**Architecture:** 后端在 news app 加一个聚合 action `GET /news/news/feed/`，逻辑抽到纯函数 `news/feed.py::build_feed()`（服务端强制可见性、统一排序与类型打散、活动仅投影公开字段）；前端新增 `ClubFeed` 容器 + 四种卡片 + 便当格样式，`HomePage` 接入并删除 mock。

**Tech Stack:** Django 6.0 + DRF（后端，`uv run python manage.py test`）/ React 19 + TypeScript + Webpack（前端，`cd frontend && npm run build`）。

**对应设计文档:** `docs/superpowers/specs/2026-07-20-homepage-club-feed-design.md`

**Pre-flight:** 在功能分支上执行（如 `feat/homepage-feed`），或由 executing skill 自动开 worktree。每个任务末尾用**精确的 `git add <文件>` 清单**提交，避免扫入仓库里既有的 `media/` 未提交改动。

---

## 文件结构

**后端**
- 新建 `news/feed.py` — 纯函数 `build_feed(*, request, limit=6)` 及私有 helper（可见性 / 排序 / 打散 / 各类型 dict 投影）。单一职责、可单测。
- 改 `news/views.py` — `NewsViewSet` 加 `feed` action；`PUBLIC_ACTIONS` 加 `"feed"`。
- 改 `news/tests.py` — 追加 `FeedTest`（`build_feed` 单测）与 `FeedEndpointTest`（端点）。

**前端**
- 新建 `frontend/src/types/feed.ts` — `FeedItem` 判别联合、`FeedResponse`、展示映射常量。
- 改 `frontend/src/api/news.ts` — 加 `newsApi.feed()`。
- 新建 `frontend/src/components/feed/FeedCards.tsx` — 四个小卡片 `FeaturedNewsCard` / `NewsCard` / `ActivityCard` / `TaskCard` 合并一处（变更同源、共享样式与 import；spec §10.1 的四文件在此合并为一个，便于一起改动与 review）。
- 新建 `frontend/src/components/ClubFeed.tsx` — 容器：拉数据、头条 + 便当格、跳转 / 空 / 加载态。
- 改 `frontend/src/pages/HomePage.tsx` — 删除 mock，渲染 `<ClubFeed/>`。
- 改 `frontend/src/styles/home.css` — 便当格与卡片样式（复用 cobalt 变量与 `.badge` 类）。

无 model / migration 改动。

---

## Task 1: 后端聚合纯函数 `build_feed`

**Files:**
- Create: `news/feed.py`
- Modify: `news/tests.py`（顶部加 import；文件末尾追加 `FeedTest`）
- Test: `news/tests.py::FeedTest`

- [ ] **Step 1: 写失败测试（追加到 `news/tests.py`）**

先把 import 补到文件顶部（在现有 `from .models import News` 之后追加）：

```python
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import timezone

from proposals.models import Proposal
from tasks.models import Task

from .feed import build_feed
```

再在 `news/tests.py` 末尾追加整个测试类：

```python
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
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `uv run python manage.py test news.tests.FeedTest`
Expected: FAIL — `ModuleNotFoundError: No module named 'news.feed'`（import 失败）。

- [ ] **Step 3: 实现 `news/feed.py`**

```python
"""首页「社团动态」聚合：新闻 / 活动(已通过申报) / 任务(登录可见) → 统一 feed。

可见性在服务端强制：任务仅登录用户可见；活动仅投影公开字段（不含预算/投票/驳回/联系方式）。
排序按 timestamp 降序 + 类型打散（避免连续 3 同类），再截断到 limit。
"""
from django.utils import timezone

from proposals.models import Proposal
from tasks.models import Task

from .models import News

# 任务「活跃」子集：未完结、未取消
_ACTIVE_TASK_STATUSES = ("pending", "in_progress", "reviewing", "review")


def _abs_url(request, value):
    """文件字段 → 绝对 URL（与 news.serializers._absolute_cover_url 行为一致）。"""
    if not value or not hasattr(value, "url"):
        return None
    url = value.url
    return request.build_absolute_uri(url) if request else url


def _activity_phase(planned_date):
    """由拟办日期推导阶段：upcoming/ongoing/ended；无日期返回 None。"""
    if planned_date is None:
        return None
    today = timezone.localdate()
    if planned_date > today:
        return "upcoming"
    if planned_date == today:
        return "ongoing"
    return "ended"


def _news_dict(news, request):
    return {
        "type": "news",
        "id": news.pk,
        "title": news.title,
        "timestamp": (news.published_at or news.created_at).isoformat(),
        "category": news.category,
        "summary": news.summary,
        "cover_image_url": _abs_url(request, news.cover_image),
        "views": news.views,
    }


def _activity_dict(proposal, request):
    """活动的公开投影：仅暴露卡片所需字段，绝不含预算/投票/驳回/联系方式/创建人。"""
    return {
        "type": "activity",
        "id": proposal.pk,
        "title": proposal.title,
        "timestamp": (proposal.approved_at or proposal.created_at).isoformat(),
        "activity_type": proposal.activity_type,
        "phase": _activity_phase(proposal.planned_date),
        "planned_date": proposal.planned_date.isoformat() if proposal.planned_date else None,
        "location": proposal.location,
        "expected_participants": proposal.expected_participants,
    }


def _assignee_dict(user):
    if user is None:
        return None
    profile = getattr(user, "profile", None)  # Profile 非自动创建；无则降级（与 tasks.SimpleUserSerializer 一致）
    return {
        "id": user.pk,
        "username": user.username,
        "nickname": getattr(profile, "nickname", "") or "",
        "avatar": (profile.avatar.url if profile and profile.avatar else None),
    }


def _task_dict(task, request):
    return {
        "type": "task",
        "id": task.pk,
        "title": task.title,
        "timestamp": (task.updated_at or task.created_at).isoformat(),
        "status": task.status,
        "priority": task.priority,
        "assignee": _assignee_dict(task.assignee),
    }


def _diversify(items):
    """轻量类型打散：若第 i 条与前两条同类型，则与后续最近的异类型交换（O(n)）。"""
    result = list(items)
    n = len(result)
    for i in range(2, n):
        t = result[i]["type"]
        if result[i - 1]["type"] == t and result[i - 2]["type"] == t:
            for j in range(i + 1, n):
                if result[j]["type"] != t:
                    result[i], result[j] = result[j], result[i]
                    break
    return result


def build_feed(*, request, limit=6):
    """聚合首页动态：``{"featured": <news>|None, "items": [<FeedItem>, ...]}``。

    - featured：头条新闻（featured=True 优先；否则阅读人数最高）；无新闻为 None，且不计入 items。
    - items：活动 / 新闻 /（登录时的）任务，按 timestamp 降序 + 类型打散，截断到 limit。
    - 可见性：任务仅登录用户可见；活动仅公开投影。
    """
    user = getattr(request, "user", None)
    is_authed = bool(user and user.is_authenticated)
    try:
        limit = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        limit = 6

    published = News.objects.filter(is_published=True)
    featured_obj = published.filter(featured=True).first()
    if featured_obj is None:
        featured_obj = published.order_by("-views", "-published_at", "-created_at").first()

    candidates = []  # [(timestamp, dict), ...] —— 时间戳用于排序

    news_qs = published.exclude(pk=featured_obj.pk) if featured_obj else published
    for n in news_qs:
        candidates.append(((n.published_at or n.created_at), _news_dict(n, request)))

    for p in Proposal.objects.filter(proposal_type="activity", status="approved"):
        candidates.append(((p.approved_at or p.created_at), _activity_dict(p, request)))

    if is_authed:
        tasks_qs = Task.objects.select_related("assignee", "assignee__profile").filter(
            status__in=_ACTIVE_TASK_STATUSES
        )
        for t in tasks_qs:
            candidates.append(((t.updated_at or t.created_at), _task_dict(t, request)))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    items = _diversify([d for _, d in candidates])[:limit]

    return {
        "featured": _news_dict(featured_obj, request) if featured_obj else None,
        "items": items,
    }
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `uv run python manage.py test news.tests.FeedTest`
Expected: PASS（9 个用例全过）。

- [ ] **Step 5: 提交**

```bash
git add news/feed.py news/tests.py
git commit -m "feat(news): 新增首页社团动态聚合 build_feed（可见性/排序/打散/公开投影）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 接入端点 `GET /news/news/feed/`

**Files:**
- Modify: `news/views.py`（`PUBLIC_ACTIONS` + 新 action；顶部 import `build_feed`）
- Modify: `news/tests.py`（末尾追加 `FeedEndpointTest`）
- Test: `news/tests.py::FeedEndpointTest`

- [ ] **Step 1: 写失败测试（追加到 `news/tests.py` 末尾）**

```python
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
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `uv run python manage.py test news.tests.FeedEndpointTest`
Expected: FAIL — 404（action 尚未注册）。

- [ ] **Step 3: 接入 view**

改 `news/views.py`：

(a) 顶部 import（在 `from .models import News, NewsView` 附近）加：

```python
from .feed import build_feed
```

(b) 把 `PUBLIC_ACTIONS` 改为包含 `"feed"`：

```python
PUBLIC_ACTIONS = frozenset({"list", "retrieve", "featured", "hot", "tags", "overview", "feed"})
```

(c) 在 `NewsViewSet` 内（与 `overview` 同级，`overview` 方法之后）加 action：

```python
    @action(detail=False, methods=["get"])
    def feed(self, request):
        """首页「社团动态」聚合：头条新闻 + 混排活动/新闻/(登录时的)任务。匿名可读。"""
        try:
            limit = int(request.query_params.get("limit", 6))
        except (TypeError, ValueError):
            limit = 6
        return Response(build_feed(request=request, limit=limit))
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `uv run python manage.py test news.tests.FeedEndpointTest`
Expected: PASS（3 个用例）。

- [ ] **Step 5: 跑整个 news app 测试，确认无回归**

Run: `uv run python manage.py test news`
Expected: PASS（原有 + 新增全过）。

- [ ] **Step 6: 提交**

```bash
git add news/views.py news/tests.py
git commit -m "feat(news): 接入 GET /news/news/feed/ 聚合接口" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 前端 `FeedItem` 类型与展示映射

**Files:**
- Create: `frontend/src/types/feed.ts`

- [ ] **Step 1: 写类型文件**

```ts
import type { NewsCategory } from "./news";

export type FeedType = "news" | "activity" | "task";

export type ActivityType = "competition" | "training" | "project" | "sharing" | "event";
export type ActivityPhase = "upcoming" | "ongoing" | "ended";
export type FeedTaskStatus = "pending" | "in_progress" | "reviewing" | "review";
export type FeedTaskPriority = "low" | "medium" | "high" | "urgent";

export interface FeedAssignee {
  id: number;
  username: string;
  nickname: string;
  avatar: string | null;
}

interface FeedItemBase {
  type: FeedType;
  id: number;
  title: string;
  timestamp: string; // ISO8601，排序依据
}

export interface NewsFeedItem extends FeedItemBase {
  type: "news";
  category: NewsCategory;
  summary: string;
  cover_image_url: string | null;
  views: number;
}

export interface ActivityFeedItem extends FeedItemBase {
  type: "activity";
  activity_type: ActivityType;
  phase: ActivityPhase | null;
  planned_date: string | null;
  location: string;
  expected_participants: number | null;
}

export interface TaskFeedItem extends FeedItemBase {
  type: "task";
  status: FeedTaskStatus;
  priority: FeedTaskPriority;
  assignee: FeedAssignee | null;
}

export type FeedItem = NewsFeedItem | ActivityFeedItem | TaskFeedItem;

export interface FeedResponse {
  featured: NewsFeedItem | null;
  items: FeedItem[];
}

// —— 展示映射 ——
export const ACTIVITY_META: Record<ActivityType, { label: string; emoji: string }> = {
  competition: { label: "比赛", emoji: "📷" },
  training: { label: "培训", emoji: "🎬" },
  project: { label: "项目", emoji: "🎥" },
  sharing: { label: "分享", emoji: "💡" },
  event: { label: "活动", emoji: "🎉" },
};

export const ACTIVITY_PHASE_LABEL: Record<ActivityPhase, string> = {
  upcoming: "即将开始",
  ongoing: "进行中",
  ended: "已结束",
};

export const FEED_TASK_STATUS_LABEL: Record<FeedTaskStatus, string> = {
  pending: "待处理",
  in_progress: "进行中",
  reviewing: "待验收",
  review: "审核中",
};

export const FEED_TASK_PRIORITY_LABEL: Record<FeedTaskPriority, string> = {
  low: "低",
  medium: "中",
  high: "高",
  urgent: "紧急",
};

// 优先级条形格数（1~3）
export const FEED_TASK_PRIORITY_BARS: Record<FeedTaskPriority, number> = {
  low: 1,
  medium: 2,
  high: 3,
  urgent: 3,
};
```

- [ ] **Step 2: 类型检查（编译）**

Run: `cd frontend && npm run build`
Expected: 构建成功（仅新增类型，不影响产物）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/types/feed.ts
git commit -m "feat(feed): 前端 FeedItem 类型与展示映射" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 前端 API 客户端 `newsApi.feed()`

**Files:**
- Modify: `frontend/src/api/news.ts`

- [ ] **Step 1: 加 import 与方法**

在 `frontend/src/api/news.ts` 顶部 import 区加：

```ts
import type { FeedResponse } from "../types/feed";
```

在 `newsApi` 对象内（与 `overview` 同级）加一项：

```ts
  // 首页「社团动态」聚合：{featured, items}（匿名可读；任务仅登录下发）
  feed: (limit = 6) => request(`/news/feed/?limit=${limit}`) as Promise<FeedResponse>,
```

- [ ] **Step 2: 编译**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/news.ts
git commit -m "feat(feed): newsApi.feed() 客户端" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 动态卡片组件

**Files:**
- Create: `frontend/src/components/feed/FeedCards.tsx`

- [ ] **Step 1: 写卡片组件**

```tsx
import { CATEGORY_BADGE_CLASS, CATEGORY_LABELS } from "../../types/news";
import {
  ACTIVITY_META,
  ACTIVITY_PHASE_LABEL,
  FEED_TASK_PRIORITY_BARS,
  FEED_TASK_STATUS_LABEL,
  type ActivityFeedItem,
  type NewsFeedItem,
  type TaskFeedItem,
  type FeedTaskPriority,
} from "../../types/feed";

function PriorityBars({ priority }: { priority: FeedTaskPriority }) {
  const on = FEED_TASK_PRIORITY_BARS[priority];
  return (
    <span className="feed-prio">
      {[0, 1, 2].map((i) => (
        <i key={i} className={i < on ? "on" : ""} />
      ))}
    </span>
  );
}

function Cover({ url, emoji = "📰" }: { url: string | null; emoji?: string }) {
  return (
    <div
      className="feed-cover"
      style={url ? { backgroundImage: `url(${url})` } : undefined}
    >
      {!url && <span className="feed-cover-emoji">{emoji}</span>}
    </div>
  );
}

export function FeaturedNewsCard({ item, onClick }: { item: NewsFeedItem; onClick: () => void }) {
  return (
    <button type="button" className="feed-featured" onClick={onClick}>
      <Cover url={item.cover_image_url} />
      <div className="feed-featured-body">
        <span className={`badge ${CATEGORY_BADGE_CLASS[item.category]}`}>
          {CATEGORY_LABELS[item.category]}
        </span>
        <h3>{item.title}</h3>
        {item.summary && <p>{item.summary}</p>}
        <div className="feed-meta">
          <span>👁 {item.views}</span>
        </div>
      </div>
    </button>
  );
}

export function NewsCard({ item, onClick }: { item: NewsFeedItem; onClick: () => void }) {
  return (
    <button type="button" className="feed-cell feed-cell--news" onClick={onClick}>
      <Cover url={item.cover_image_url} />
      <div className="feed-cell-body">
        <span className={`badge ${CATEGORY_BADGE_CLASS[item.category]}`}>
          {CATEGORY_LABELS[item.category]}
        </span>
        <h4>{item.title}</h4>
        <div className="feed-meta">
          <span>👁 {item.views}</span>
        </div>
      </div>
    </button>
  );
}

export function ActivityCard({ item, onClick }: { item: ActivityFeedItem; onClick: () => void }) {
  const meta = ACTIVITY_META[item.activity_type] ?? { label: "活动", emoji: "🎉" };
  return (
    <button type="button" className="feed-cell feed-cell--activity" onClick={onClick}>
      <div className="feed-act-head">
        <span className="badge badge-brand">{meta.label}</span>
        <span className="feed-emoji">{meta.emoji}</span>
      </div>
      <h4>{item.title}</h4>
      <div className="feed-act-foot">
        {item.planned_date && <span>📅 {item.planned_date}</span>}
        {item.location && <span>📍 {item.location}</span>}
        {item.expected_participants != null && <span>👥 {item.expected_participants}</span>}
      </div>
      {item.phase && (
        <span className={`feed-phase feed-phase--${item.phase}`}>
          {ACTIVITY_PHASE_LABEL[item.phase]}
        </span>
      )}
    </button>
  );
}

export function TaskCard({ item, onClick }: { item: TaskFeedItem; onClick: () => void }) {
  return (
    <button type="button" className="feed-cell feed-cell--task" onClick={onClick}>
      <div className="feed-task-head">
        <span className={`feed-status feed-status--${item.status}`}>
          {FEED_TASK_STATUS_LABEL[item.status]}
        </span>
        <PriorityBars priority={item.priority} />
      </div>
      <h4>{item.title}</h4>
      <div className="feed-meta">
        {item.assignee ? `@${item.assignee.nickname || item.assignee.username}` : "未指派"}
      </div>
    </button>
  );
}
```

- [ ] **Step 2: 编译**

Run: `cd frontend && npm run build`
Expected: 成功（卡片未被引用，但需通过类型检查；若 tsconfig 的 `noUnusedLocals` 报警，去掉未用的 import）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/feed/FeedCards.tsx
git commit -m "feat(feed): 动态卡片组件（头条/新闻/活动/任务）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `ClubFeed` 容器

**Files:**
- Create: `frontend/src/components/ClubFeed.tsx`

- [ ] **Step 1: 写容器组件**

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { newsApi } from "../api/news";
import { useLoginModal } from "./LoginModalProvider";
import { ActivityCard, FeaturedNewsCard, NewsCard, TaskCard } from "./feed/FeedCards";
import type { FeedItem, FeedResponse } from "../types/feed";

interface Props {
  // HomePage 的 user 状态：这里只需 id（登录态判定 + 重拉依赖）与真值（点击活动时游客/成员分流）
  user: { id: number } | null;
}

export default function ClubFeed({ user }: Props) {
  const [data, setData] = useState<FeedResponse | null>(null);
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();

  // 用户身份变化（登录/登出）时重拉，让任务格随之出现/消失
  useEffect(() => {
    newsApi.feed().then(setData).catch(() => setData(null));
  }, [user?.id]);

  const goNews = (id: number) => navigate(`/news/${id}`);
  const goTask = (id: number) => navigate(`/tasks/${id}`);
  const goActivity = (id: number) => {
    if (user) navigate(`/activity/${id}`);
    else openLogin(`/activity/${id}`); // 游客点活动 → 弹登录（引流）
  };

  const open = (item: FeedItem) => () => {
    if (item.type === "news") goNews(item.id);
    else if (item.type === "task") goTask(item.id);
    else goActivity(item.id);
  };

  const featured = data?.featured ?? null;
  const items = data?.items ?? [];
  const sizeFor = (i: number): "large" | "medium" | "small" =>
    i === 0 ? "large" : i === 1 ? "medium" : "small";

  return (
    <section>
      <div className="section-head">
        <div>
          <div className="eyebrow">CLUB · ACTIVITY</div>
          <h2 className="section-title">
            <span className="bar" /> 社团动态
          </h2>
        </div>
        <a
          className="section-link"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("/news");
          }}
        >
          全部动态
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </a>
      </div>

      {!data ? (
        <div className="feed-empty">加载中…</div>
      ) : !featured && items.length === 0 ? (
        <div className="feed-empty">暂无动态</div>
      ) : (
        <>
          {featured && <FeaturedNewsCard item={featured} onClick={() => goNews(featured.id)} />}
          {items.length > 0 && (
            <div className="feed-bento">
              {items.map((item, i) => (
                <div key={`${item.type}-${item.id}`} className={`feed-cell-wrap feed-cell-wrap--${sizeFor(i)}`}>
                  {item.type === "news" ? (
                    <NewsCard item={item} onClick={open(item)} />
                  ) : item.type === "activity" ? (
                    <ActivityCard item={item} onClick={open(item)} />
                  ) : (
                    <TaskCard item={item} onClick={open(item)} />
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
```

- [ ] **Step 2: 编译**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/ClubFeed.tsx
git commit -m "feat(feed): ClubFeed 容器（便当格 + 跳转/空/加载态）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 首页接入 `ClubFeed`，移除 mock

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: 删除 mock 并接入**

(a) 删除 `HomePage.tsx` 顶部的 mock 定义——即 `interface Activity {...}`、`const ACTIVITIES: Activity[] = [...]`、`const STATUS_BADGE: ...` 三个块（原文件约第 14–37 行）。

(b) 在顶部 import 区加：

```ts
import ClubFeed from "../components/ClubFeed";
```

(c) 把右栏 `<div className="home-main"> ... </div>` 里的整段 `<section>...activity-grid...</section>` 替换为：

```tsx
          <div className="home-main">
            <ClubFeed user={user} />
          </div>
```

> `user` 状态与 `go()`/`navigate`/`useLoginModal` 保持不变（Hero 与快速入口仍用）；`EqBars` 仍被 Hero 用到，不要删。

- [ ] **Step 2: 编译**

Run: `cd frontend && npm run build`
Expected: 成功（不再有未用的 `Activity`/`STATUS_BADGE` 残留）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/HomePage.tsx
git commit -m "feat(home): 首页社团动态接入 ClubFeed，移除 mock" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 便当格与卡片样式

**Files:**
- Modify: `frontend/src/styles/home.css`（在文件末尾追加；复用 cobalt 变量与 `.badge` 类）

- [ ] **Step 1: 追加样式**

```css
/* ── 社团动态 feed（头条 + 便当格）── */
.feed-empty { padding: var(--s-16) 0; text-align: center; color: var(--muted); font-size: 14px; }
.feed-meta { font-size: 12px; color: var(--muted); display: flex; gap: var(--s-3); flex-wrap: wrap; }

/* 头条 */
.feed-featured { display: flex; width: 100%; margin-top: var(--s-5); text-align: left;
  background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-lg); overflow: hidden;
  cursor: pointer; color: inherit; font: inherit; transition: transform var(--dur-1), box-shadow var(--dur-1); }
.feed-featured:hover { transform: translateY(-2px); box-shadow: 0 8px 24px oklch(0.2 0.02 250 / .10); }
.feed-featured .feed-featured-body { flex: 1; padding: var(--s-5) var(--s-6); display: flex; flex-direction: column; justify-content: center; gap: var(--s-2); }
.feed-featured h3 { font-size: 20px; line-height: 1.3; margin: var(--s-1) 0; color: var(--fg); }
.feed-featured p { font-size: 14px; color: var(--muted); line-height: 1.6; margin: 0; }

/* 封面（公共） */
.feed-cover { background-size: cover; background-position: center; display: flex; align-items: center; justify-content: center; }
.feed-featured .feed-cover { flex: 0 0 46%; min-height: 180px; background-color: oklch(0.97 0.01 250); }
.feed-cover-emoji { font-size: 40px; opacity: .8; }

/* 便当格 */
.feed-bento { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--s-5); margin-top: var(--s-5); }
.feed-cell-wrap { display: flex; }
.feed-cell-wrap--large { grid-column: span 2; }
.feed-cell-wrap--medium { grid-column: span 1; }
.feed-cell-wrap--small { grid-column: span 1; }

/* 卡片本体（button 重置） */
.feed-cell { display: flex; flex-direction: column; width: 100%; text-align: left; cursor: pointer;
  color: inherit; font: inherit; border-radius: var(--r-lg); padding: var(--s-4); gap: var(--s-2);
  border: 1px solid var(--line); background: var(--bg); transition: transform var(--dur-1), box-shadow var(--dur-1); }
.feed-cell:hover { transform: translateY(-2px); box-shadow: 0 8px 24px oklch(0.2 0.02 250 / .10); }
.feed-cell h4 { font-size: 14px; line-height: 1.4; margin: 0; color: var(--fg); }
.feed-cell-wrap--large .feed-cell { padding: var(--s-5); }

/* 新闻格 */
.feed-cell--news { padding: 0; overflow: hidden; }
.feed-cell--news .feed-cover { height: 96px; min-height: 0; }
.feed-cell--news .feed-cell-body { padding: var(--s-3); display: flex; flex-direction: column; gap: 4px; flex: 1; }

/* 活动格（暖色块，无封面） */
.feed-cell--activity { background: linear-gradient(160deg, oklch(0.98 0.02 75), var(--bg)); border-color: oklch(0.88 0.06 70); }
.feed-act-head { display: flex; align-items: flex-start; justify-content: space-between; }
.feed-emoji { font-size: 28px; }
.feed-act-foot { display: flex; flex-wrap: wrap; gap: var(--s-3); font-size: 12px; color: var(--muted); }
.feed-phase { align-self: flex-start; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: var(--r-pill); margin-top: var(--s-1); }
.feed-phase--upcoming { background: oklch(0.95 0.06 85); color: oklch(0.42 0.1 70); }
.feed-phase--ongoing { background: oklch(0.95 0.05 150); color: oklch(0.4 0.12 150); }
.feed-phase--ended { background: var(--line); color: var(--muted); }

/* 任务格（冷色，成员可见） */
.feed-cell--task { background: linear-gradient(160deg, oklch(0.97 0.02 240), var(--bg)); border-color: oklch(0.88 0.04 240); }
.feed-task-head { display: flex; align-items: center; justify-content: space-between; }
.feed-status { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: var(--r-pill); }
.feed-status--pending { background: oklch(0.96 0.06 85); color: oklch(0.42 0.1 70); }
.feed-status--in_progress { background: oklch(0.95 0.05 160); color: oklch(0.4 0.12 160); }
.feed-status--reviewing, .feed-status--review { background: oklch(0.95 0.05 250); color: oklch(0.42 0.1 250); }
.feed-prio { display: inline-flex; gap: 2px; }
.feed-prio i { width: 4px; height: 11px; border-radius: 2px; background: var(--line); display: inline-block; }
.feed-prio i.on { background: var(--brand-600); }

/* 响应式：与原 .activity-grid 断点一致 */
@media (max-width: 1024px) {
  .feed-bento { grid-template-columns: repeat(2, 1fr); }
  .feed-cell-wrap--large { grid-column: span 2; }
}
@media (max-width: 640px) {
  .feed-bento { grid-template-columns: 1fr; }
  .feed-cell-wrap--large { grid-column: span 1; }
  .feed-featured { flex-direction: column; }
  .feed-featured .feed-cover { flex: none; width: 100%; min-height: 140px; }
}
```

- [ ] **Step 2: 构建**

Run: `cd frontend && npm run build`
Expected: 成功（CSS 不影响编译；产物含新样式）。

- [ ] **Step 3: 手动联调验证**

Run dev servers（后端 `uv run python manage.py runserver`；前端 `cd frontend && npm run dev`），打开首页：
- 游客态：看到 头条新闻 + 活动 + 新闻 格子，**无任务格**。
- 登录后：任务格出现；点任务跳 `/tasks/:id`。
- 点新闻跳 `/news/:id`（直接可达）；点活动，游客弹登录、登录后跳 `/activity/:id`。
- 无内容时显示"暂无动态"。

Expected: 上述行为全部符合。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/styles/home.css
git commit -m "style(home): 社团动态便当格与卡片样式" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 完成判据

- `uv run python manage.py test news` 全绿（含 `FeedTest` / `FeedEndpointTest`）。
- `cd frontend && npm run build` 成功。
- 首页游客/登录两态均符合设计的「头条 + 便当格」与可见性矩阵（见 spec §9）。
