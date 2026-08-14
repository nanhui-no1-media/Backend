from django.conf import settings
from django.db import models


class Proposal(models.Model):
    """申报：意见反馈（单向投递箱）。

    活动已分离为独立概念「活动」(activities app，ADR 0007)；本表仅承载意见反馈 /
    举报。反馈无投票、无打回，社长仅通过 / 拒绝；跟进走线下其他渠道。
    """

    TYPE_CHOICES = [
        ("feedback", "意见反馈"),
    ]
    STATUS_CHOICES = [
        ("pending_approval", "待社长审批"),
        ("approved", "已通过"),
        ("rejected", "已拒绝"),
        ("withdrawn", "已撤回"),
    ]
    FEEDBACK_CATEGORY_CHOICES = [
        ("suggestion", "建议"),
        ("complaint", "投诉"),
        ("report", "举报"),
        ("other", "其他"),
    ]

    proposal_type = models.CharField("类型", max_length=10, choices=TYPE_CHOICES, default="feedback")
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="pending_approval")

    title = models.CharField("标题", max_length=200)
    description = models.TextField("详细说明", blank=True, default="")

    # 意见反馈专属字段
    feedback_category = models.CharField("反馈类别", max_length=20, choices=FEEDBACK_CATEGORY_CHOICES, blank=True, default="")
    contact = models.CharField("联系方式（选填）", max_length=100, blank=True, default="")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_proposals", verbose_name="创建人",
    )

    # 审批记录
    reject_reason = models.TextField("拒绝理由", blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_proposals", verbose_name="审核人",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    approved_at = models.DateTimeField("通过时间", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "申报"
        verbose_name_plural = "申报"
        ordering = ["-created_at"]
        permissions = [
            ("approve_proposal", "可审批反馈"),
            ("view_feedback", "可查看意见反馈/举报"),
        ]

    def __str__(self):
        return f"{self.get_proposal_type_display()}: {self.title}"


# 申报附件（ProposalAttachment）已统一到独立 attachments app：见 attachments/models.py。
# 删除申报时，CASCADE 经统一附件的可空 proposal 外键连带删除其附件行，再由该 app 的
# post_delete 信号回收磁盘文件——故此处不再需要内嵌附件模型。
