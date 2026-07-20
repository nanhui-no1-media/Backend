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
