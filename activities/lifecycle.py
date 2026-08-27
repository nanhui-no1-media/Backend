"""活动生命周期模块（ADR 0007 / 0011 / 遵循 ADR 0003：状态机与访问控制分离）。

独占活动的状态机与守卫，对外暴露纯领域逻辑。

- 众议 / 调研：open → closed；到 ``end_at`` 惰性结算。
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
    """活动创建时的初始状态：``start_at`` 在未来 → scheduled（待开始）；否则众议/展示/调研=open、征集=collecting。

    供序列化器 create 共用的单一事实源。``start_at`` 为 None 表示不排期（创建即开放）。
    """
    if start_at is not None and start_at > timezone.now():
        return SCHEDULED
    if activity_type in ("deliberation", "exhibition", "survey"):
        return OPEN
    if activity_type == "collection":
        return COLLECTING
    raise ValueError(f"未知活动类型: {activity_type!r}")


def transition_due_starts():
    """惰性开放：把已到 ``start_at`` 的 scheduled 活动翻转为开放态
    （众议/展示/调研→open / 征集→collecting）。在 list/get/vote/submit/respond 入口调用。

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
    """是否可编辑（改 start_at/end_at/正文/选项/配置）：仅 scheduled（待开始）期间。开放后锁定。

    调研 Schema 另见 ``can_edit_schema``（开放且零作答时仍可改问卷，标题/时间仍走本谓词）。
    """
    return activity.status == SCHEDULED


def can_edit_schema(activity):
    """调研问卷 Schema 可否改：类型=调研，且待开始，或开放中尚无作答。"""
    if activity.type != "survey":
        return False
    if activity.status == SCHEDULED:
        return True
    if activity.status == OPEN:
        qid = activity.questionnaire_id
        if not qid:
            return True
        return not QuestionnaireResponse.objects.filter(questionnaire_id=qid).exists()
    return False


def can_respond(activity, user):
    """调研作答守卫：类型=调研、状态=open。公开受众任何人；仅成员须登录。

    审核通过由视图另判；已登录重复提交由视图 + 部分唯一约束收口。
    """
    if activity.type != "survey" or activity.status != OPEN:
        return False
    if activity.audience == "public":
        return True
    return bool(getattr(user, "is_authenticated", False))


# ---- 众议 --------------------------------------------------------------

def can_vote(activity, user):
    """投票守卫：众议始终可投；展示仅 ``voting_enabled`` 时——状态=open、用户已认证。

    展示的投票是否启用取决于 ``voting_enabled``：默认 False（纯陈列，仅赞/踩），
    True 时才放行投票。已验证由 IsVerified 把关。
    """
    if not user.is_authenticated:
        return False
    if activity.type == "deliberation":
        return activity.status == OPEN
    if activity.type == "exhibition":
        return activity.voting_enabled and activity.status == OPEN
    return False


def can_rate(activity, user):
    """展示评分守卫：类型=展示、状态=open、用户已认证。"""
    return (
        user.is_authenticated
        and activity.type == "exhibition"
        and activity.status == OPEN
    )


def can_curate(activity, user):
    """展示布展守卫：类型=展示、状态∈{待开始,展示中}、用户已认证。

    策展人(发起人 or change_activity)的角色/归属判定由 CanModifyActivity 权限类
    在 get_object 时把关;此处只管「此刻能否布展」的状态机条件——加/删/导入展品
    在待开始与展示中都可进行,仅已结束(closed)禁止。改展品(标题)另见 can_edit_exhibit。
    """
    return (
        user.is_authenticated
        and activity.type == "exhibition"
        and activity.status in (SCHEDULED, OPEN)
    )


def can_edit_exhibit(activity, user):
    """展示展品改标题守卫：类型=展示、状态=待开始(scheduled)、用户已认证。

    与 can_curate 的差异：展示中(open)仍可加/删/导入展品，但**改**已上架展品
    （可能已有投票/赞踩）仅限待开始期，开放后锁定。
    """
    return (
        user.is_authenticated
        and activity.type == "exhibition"
        and activity.status == SCHEDULED
    )


def can_close(activity, user):
    """提前关闭守卫：发起人或持 activities.change_activity，且状态允许关。

    众议/展示/调研须 open；征集须 collecting。归属与角色仍由 CanModifyActivity 把关；
    此处把视图曾内联的状态条件收口，供 close 动作调用。
    """
    if not user.is_authenticated:
        return False
    if not (activity.creator_id == user.pk or user.has_perm("activities.change_activity")):
        return False
    if activity.type in ("deliberation", "exhibition", "survey"):
        return activity.status == OPEN
    if activity.type == "collection":
        return activity.status == COLLECTING
    return False


def transition_overdue():
    """惰性结算：把已到 ``end_at`` 的开放态众议/展示/调研从 open 流转到 closed。

    在 list/get/vote/rate/respond 入口调用。逐行条件更新保证每条活动只被一个请求流转（并发安全；
    Django 无内置调度，此惰性方式无需 cron）。征集另有满额流转（``maybe_close_collection_on_cap``）。
    """
    now = timezone.now()
    overdue = Activity.objects.filter(
        type__in=("deliberation", "exhibition", "survey"), status=OPEN, end_at__lte=now,
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


def collection_close_target(activity):
    """征集收件结束的目标态：启用复审 → reviewing；关闭复审 → archived（跳过复审）。

    单一事实源——``close`` 动作与 ``maybe_close_collection_on_cap`` 共用此规则。
    """
    return REVIEWING if activity.review_enabled else ARCHIVED


def maybe_close_collection_on_cap(activity):
    """满额自动关闭：作品数达 ``max_submissions`` 时 collecting→reviewing/archived。返回是否触发。

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
        changed = Activity.objects.filter(
            pk=activity.pk, status=COLLECTING,
        ).update(status=collection_close_target(activity), updated_at=timezone.now())
        return bool(changed)
    return False


# 延迟导入打破 activities 内部循环（lifecycle ↔ models 同 app，无环；保留供未来跨引用）。
from .models import Activity, QuestionnaireResponse, Submission  # noqa: E402
