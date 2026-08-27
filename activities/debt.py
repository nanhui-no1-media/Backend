"""活动债谓词（#82）：收件箱活动行与列表/详情 ``owed`` 的单一事实源。

``activity_debts_for`` 的 queryset 由调用方先过滤身份；序列化 ``owed_for``
在此判定已验证（访客与未验证得到 None；超管经后台委任通道计入）。
"""
from django.db.models import Exists, OuterRef, Q

from accounts.models import is_verified
from reviews.visibility import public_q

from .lifecycle import COLLECTING, OPEN, transition_due_starts, transition_overdue
from .models import Activity, Ballot, Submission

REASON_VOTE = "vote"
REASON_SUBMIT = "submit"


def activity_debt_reason(activity, *, has_ballot, has_submission):
    """返回 ``vote`` / ``submit`` / None。"""
    if activity.type == "deliberation" and activity.status == OPEN and not has_ballot:
        return REASON_VOTE
    if activity.type == "collection" and activity.status == COLLECTING and not has_submission:
        return REASON_SUBMIT
    if (
        activity.type == "exhibition"
        and activity.status == OPEN
        and activity.voting_enabled
        and not has_ballot
    ):
        return REASON_VOTE
    return None  # 调研等其余类型不算社团义务，不进债


def owed_for(activity, user):
    """序列化 ``owed``：``vote`` / ``submit`` / None。优先用 annotate 的 Exists。"""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if not is_verified(user):
        return None
    has_ballot = getattr(activity, "_has_ballot", None)
    if has_ballot is None:
        has_ballot = any(b.voter_id == user.pk for b in activity.ballots.all())
    has_submission = getattr(activity, "_has_submission", None)
    if has_submission is None:
        has_submission = any(s.submitter_id == user.pk for s in activity.submissions.all())
    return activity_debt_reason(
        activity, has_ballot=bool(has_ballot), has_submission=bool(has_submission),
    )


def annotate_activity_debt(qs, user):
    """给活动 queryset 标 ``_has_ballot`` / ``_has_submission``（Exists，避免 N+1）。"""
    if not user or not user.is_authenticated:
        return qs
    return qs.annotate(
        _has_ballot=Exists(
            Ballot.objects.filter(activity_id=OuterRef("pk"), voter=user),
        ),
        _has_submission=Exists(
            Submission.objects.filter(activity_id=OuterRef("pk"), submitter=user),
        ),
    )


def activity_debts_for(user):
    """当前用户仍欠行动的公开活动（已跑惰性状态机）。"""
    transition_due_starts()
    transition_overdue()
    qs = annotate_activity_debt(
        Activity.objects.filter(public_q("activity")).select_related(
            "creator", "creator__profile", "publication_review",
        ),
        user,
    )
    return qs.filter(
        Q(type="deliberation", status=OPEN, _has_ballot=False)
        | Q(type="collection", status=COLLECTING, _has_submission=False)
        | Q(type="exhibition", status=OPEN, voting_enabled=True, _has_ballot=False)
    )
