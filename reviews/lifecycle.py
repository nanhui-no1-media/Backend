"""审核状态机（ADR-0003：状态转移不是访问控制，与 permission_classes 分离）。"""
from django.utils import timezone

from .models import Review

APPROVE = "approve"
REJECT = "reject"
REMOVE = "remove"

_ALLOWED = {
    APPROVE: (Review.STATUS_PENDING, Review.STATUS_REMOVED),
    REJECT: (Review.STATUS_PENDING,),
    REMOVE: (Review.STATUS_APPROVED,),
}


class TransitionDenied(Exception):
    """当前状态不允许该审核动作。"""


def open_review(*, news=None, activity=None, tutorial=None, actor, force_publish=None):
    """为新对象打开一条审核。免审发布者直接通过，否则待审。

    是否免审由 ``reviews.force_publish`` 判定（调用方不必再查权限）。
    """
    if force_publish is None:
        force_publish = bool(actor and actor.has_perm("reviews.force_publish"))
    kwargs = {"news": news, "activity": activity, "tutorial": tutorial}
    if force_publish:
        return Review.objects.create(
            **kwargs,
            status=Review.STATUS_APPROVED,
            reviewer=actor,
            reviewed_at=timezone.now(),
        )
    return Review.objects.create(**kwargs, status=Review.STATUS_PENDING)


def apply(action, review, user, *, comment=""):
    """执行通过 / 驳回 / 下架。非法转移抛 TransitionDenied。"""
    allowed = _ALLOWED.get(action)
    if allowed is None or review.status not in allowed:
        raise TransitionDenied("当前状态不可执行该审核动作")
    if action == REJECT and not (comment or "").strip():
        raise TransitionDenied("请填写驳回评语")

    review.reviewer = user
    review.reviewed_at = timezone.now()
    if action == APPROVE:
        review.status = Review.STATUS_APPROVED
        review.comment = (comment or "").strip()
    elif action == REJECT:
        review.status = Review.STATUS_REJECTED
        review.comment = comment.strip()
    else:
        review.status = Review.STATUS_REMOVED
        review.comment = (comment or "").strip()
    review.save(update_fields=["status", "comment", "reviewer", "reviewed_at", "updated_at"])
    return review
