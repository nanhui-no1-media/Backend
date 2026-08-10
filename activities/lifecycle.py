"""活动生命周期模块（ADR 0007 / 遵循 ADR 0003：状态机与访问控制分离）。

独占活动的状态机与守卫，对外暴露纯领域逻辑。

- 众议：open（投票中）→ closed（已截止结算）；到 ``end_at`` 惰性结算。
- 征集：collecting → reviewing → archived；满 ``max_submissions`` 自动 collecting→reviewing。
"""

from django.utils import timezone

# 状态常量（与 models.STATUS_CHOICES 对齐）
SCHEDULED = "scheduled"    # 排期：start_at 之前，待开始
OPEN = "open"              # 众议：投票中
CLOSED = "closed"          # 众议：已截止结算
COLLECTING = "collecting"  # 征集：收件中
REVIEWING = "reviewing"    # 征集：复审中
ARCHIVED = "archived"      # 征集：已归档


def initial_status(activity_type, start_at=None):
    """活动创建时的初始状态：``start_at`` 在未来 → scheduled（待开始）；否则众议=open / 征集=collecting。

    供序列化器 create 共用的单一事实源。``start_at`` 为 None 表示不排期（创建即开放）。
    """
    if start_at is not None and start_at > timezone.now():
        return SCHEDULED
    if activity_type == "deliberation":
        return OPEN
    if activity_type == "collection":
        return COLLECTING
    if activity_type == "exhibition":
        return OPEN
    raise ValueError(f"未知活动类型: {activity_type!r}")


def transition_due_starts():
    """惰性开放：把已到 ``start_at`` 的 scheduled 活动翻转为开放态
    （众议→open / 征集→collecting）。在 list/get/vote/submit 入口调用。

    逐行条件更新（status=scheduled）保证并发安全——多个读者同时触达时只有一个请求真正翻转。
    """
    now = timezone.now()
    due = Activity.objects.filter(status=SCHEDULED, start_at__lte=now)
    opened = []
    for activity in due:
        # 征集 → collecting；众议/展示 → open
        target = COLLECTING if activity.type == "collection" else OPEN
        changed = Activity.objects.filter(pk=activity.pk, status=SCHEDULED).update(
            status=target, updated_at=now,
        )
        if changed:
            opened.append(activity.pk)
    return opened


def can_edit(activity):
    """是否可编辑（改 start_at/end_at/正文/选项/配置）：仅 scheduled（待开始）期间。开放后锁定。"""
    return activity.status == SCHEDULED


# ---- 众议 --------------------------------------------------------------

def can_vote(activity, user):
    """投票守卫：众议，或展示（启用投票时）——类型∈{众议,展示}、状态=open、用户已认证。

    展示的投票是可选的；无选项时投票动作会因「选项不存在」自行拒绝。已验证由 IsVerified 把关。
    """
    return (
        user.is_authenticated
        and activity.type in ("deliberation", "exhibition")
        and activity.status == OPEN
    )


def can_rate(activity, user):
    """展示评分守卫：类型=展示、状态=open、用户已认证。"""
    return (
        user.is_authenticated
        and activity.type == "exhibition"
        and activity.status == OPEN
    )


def can_close(activity, user):
    """提前关闭守卫：发起人，或持 activities.change_activity 权限者。

    「此刻能否关」的状态机条件（众议须 open、征集须 collecting）由视图的 close 动作
    在调用前校验；此处只判归属与角色。
    """
    return user.is_authenticated and (
        activity.creator_id == user.pk or user.has_perm("activities.change_activity")
    )


def transition_overdue():
    """惰性结算：把已到 ``end_at`` 的开放态众议/展示从 open 流转到 closed。

    在 list/get/vote/rate 入口调用。逐行条件更新保证每条活动只被一个请求流转（并发安全；
    Django 无内置调度，此惰性方式无需 cron）。征集另有满额流转（``maybe_close_collection_on_cap``）。
    """
    now = timezone.now()
    overdue = Activity.objects.filter(
        type__in=("deliberation", "exhibition"), status=OPEN, end_at__lte=now,
    )
    closed_pks = []
    for activity in overdue:
        changed = Activity.objects.filter(
            pk=activity.pk, status=OPEN,
        ).update(status=CLOSED, updated_at=now)
        if changed:
            closed_pks.append(activity.pk)
    return closed_pks


# ---- 征集 --------------------------------------------------------------

def can_submit(activity, user):
    """征集投稿守卫：类型=征集、状态=collecting、用户已认证。

    「已验证」由视图的 IsVerified 把关；满额由视图在投稿后用
    ``maybe_close_collection_on_cap`` 收口。
    """
    return (
        user.is_authenticated
        and activity.type == "collection"
        and activity.status == COLLECTING
    )


def maybe_close_collection_on_cap(activity):
    """满额自动关闭：作品数达 ``max_submissions`` 时 collecting→reviewing。返回是否触发。

    逐行条件更新（status=collecting）保证并发安全——多个投稿者同时触达上限时只有一个
    请求真正翻转状态。``max_submissions`` 为 None（不限）时永不触发。
    """
    if activity.type != "collection" or activity.status != COLLECTING:
        return False
    if not activity.max_submissions:
        return False
    # 用直接模型查询计数，绕开视图预取缓存（submit 时 activity 携带空的预取 submissions，
    # 用 activity.submissions.count() 会读到缓存 0 而非真实 1）。
    count = Submission.objects.filter(activity_id=activity.pk).count()
    if count >= activity.max_submissions:
        # 启用复审 → reviewing；关闭复审 → 直接归档（跳过复审）
        target = REVIEWING if activity.review_enabled else ARCHIVED
        changed = Activity.objects.filter(
            pk=activity.pk, status=COLLECTING,
        ).update(status=target, updated_at=timezone.now())
        return bool(changed)
    return False


def maybe_close_deliberation_on_full_vote(activity):
    """全员投完即提前结算：众议 open 状态下，若已投票数 ≥ 已验证成员数，翻 closed。

    分母 = 已验证成员数（``accounts.verified_member_count``，纯计算不含超管）。
    在 vote 动作里调用（只有投票会改变票数）。逐行条件更新保证并发安全。
    """
    if activity.type != "deliberation" or activity.status != OPEN:
        return False
    from accounts.models import verified_member_count

    total = verified_member_count()
    if total <= 0:
        return False
    # 绕开预取缓存：用 Ballot 模型直接计票。
    if Ballot.objects.filter(activity_id=activity.pk).count() >= total:
        changed = Activity.objects.filter(
            pk=activity.pk, status=OPEN,
        ).update(status=CLOSED, updated_at=timezone.now())
        return bool(changed)
    return False


# 延迟导入打破 activities 内部循环（lifecycle ↔ models 同 app，无环；保留供未来跨引用）。
from .models import Activity, Ballot, Submission  # noqa: E402
