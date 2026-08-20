"""公开可见性：审核轴只门控「公开展示」，不改对象自身生命周期。"""
from django.core.exceptions import ObjectDoesNotExist

from .models import Review


def public_news_kwargs():
    """新闻公开读过滤：已发布且审核通过。"""
    return {"is_published": True, "review__status": Review.STATUS_APPROVED}


def review_status_of(obj):
    """读对象当前审核状态；尚无审核记录时返回 None（不抛 OneToOne 的 DoesNotExist）。"""
    try:
        review = obj.review
    except ObjectDoesNotExist:
        return None
    return review.status if review else None
