"""统一审核：正交于对象自身生命周期，只门控公开可见性。

一条 Review 恰好挂一个父级（新闻或活动；教程在 T08 落地后再加 FK）。
状态机见 lifecycle.py；此处只给字段与约束。
"""
from django.conf import settings
from django.db import models


class Review(models.Model):
    """审核记录：待审 → 通过 / 驳回，通过后可下架。"""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_REMOVED = "removed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "待审"),
        (STATUS_APPROVED, "通过"),
        (STATUS_REJECTED, "驳回"),
        (STATUS_REMOVED, "下架"),
    ]

    status = models.CharField("状态", max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    comment = models.TextField("评语", blank=True, default="")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="moderated_reviews", verbose_name="审核人",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)

    news = models.OneToOneField(
        "news.News", on_delete=models.CASCADE,
        null=True, blank=True, related_name="review", verbose_name="新闻",
    )
    activity = models.OneToOneField(
        "activities.Activity", on_delete=models.CASCADE,
        null=True, blank=True, related_name="publication_review", verbose_name="活动",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "审核"
        verbose_name_plural = "审核"
        ordering = ["-created_at"]
        permissions = [
            ("force_publish", "可免审发布"),
            ("moderate", "可审核内容"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(news__isnull=False, activity__isnull=True)
                    | models.Q(news__isnull=True, activity__isnull=False)
                ),
                name="review_exactly_one_parent",
            ),
        ]

    def __str__(self):
        target = self.news or self.activity
        return f"{self.get_status_display()}:{target}"
