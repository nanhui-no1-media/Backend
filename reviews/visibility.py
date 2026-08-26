"""公开可见性：审核轴只门控「公开展示」，不改对象自身生命周期。"""
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from .models import Review


def public_news_kwargs():
    """新闻公开读过滤：已发布且审核通过。"""
    return {"is_published": True, "review__status": Review.STATUS_APPROVED}


def public_activity_q():
    """活动公开读：已过审，或尚无审核行（存量 ORM 数据 / 未接入前的测试夹具）。"""
    return Q(publication_review__status=Review.STATUS_APPROVED) | Q(publication_review__isnull=True)


def public_tutorial_q():
    """教程公开读：仅已过审（新模块，创建必开审核行，无存量夹具例外）。"""
    return Q(review__status=Review.STATUS_APPROVED)


def review_record_of(obj, related="review"):
    """读对象上的审核行；尚无记录时返回 None（不抛 OneToOne 的 DoesNotExist）。"""
    try:
        review = getattr(obj, related)
    except ObjectDoesNotExist:
        return None
    return review


def review_status_of(obj, related="review"):
    """读对象当前审核状态；尚无审核记录时返回 None。"""
    review = review_record_of(obj, related=related)
    return review.status if review else None


def review_comment_for(obj, user, *, related="review", owner_id):
    """审核评语：仅作者/持 moderate 者可见；其余（含公众）得到空串。"""
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    if user.pk != owner_id and not user.has_perm("reviews.moderate"):
        return ""
    review = review_record_of(obj, related=related)
    return (review.comment or "") if review else ""
