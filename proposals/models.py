import os
import uuid

from django.conf import settings
from django.db import models


def proposal_attachment_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"proposal_attachments/proposal_{instance.proposal_id}/{uuid.uuid4().hex}{ext}"


class Proposal(models.Model):
    """申报：活动申报 or 意见反馈"""

    TYPE_CHOICES = [
        ("activity", "活动申报"),
        ("feedback", "意见反馈"),
    ]
    STATUS_CHOICES = [
        ("voting", "投票中"),            # 仅活动申报
        ("pending_approval", "待社长审批"),
        ("returned", "已打回"),          # 创建人可编辑后重新提交
        ("approved", "已通过"),
        ("rejected", "已拒绝"),
        ("withdrawn", "已撤回"),
    ]
    ACTIVITY_TYPE_CHOICES = [
        ("competition", "比赛"),
        ("training", "培训"),
        ("project", "项目"),
        ("sharing", "分享"),
        ("event", "活动"),
    ]
    FEEDBACK_CATEGORY_CHOICES = [
        ("suggestion", "建议"),
        ("complaint", "投诉"),
        ("report", "举报"),
        ("other", "其他"),
    ]

    proposal_type = models.CharField("类型", max_length=10, choices=TYPE_CHOICES)
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="pending_approval")

    title = models.CharField("标题", max_length=200)
    description = models.TextField("详细说明", blank=True, default="")

    # 活动申报专属字段
    activity_type = models.CharField("活动类型", max_length=20, choices=ACTIVITY_TYPE_CHOICES, blank=True, default="")
    planned_date = models.DateField("拟办日期", null=True, blank=True)
    location = models.CharField("地点", max_length=200, blank=True, default="")
    expected_participants = models.PositiveIntegerField("预计人数", null=True, blank=True)
    budget = models.DecimalField("预算", max_digits=10, decimal_places=2, null=True, blank=True)

    # 意见反馈专属字段
    feedback_category = models.CharField("反馈类别", max_length=20, choices=FEEDBACK_CATEGORY_CHOICES, blank=True, default="")
    contact = models.CharField("联系方式（选填）", max_length=100, blank=True, default="")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_proposals", verbose_name="创建人",
    )

    # 投票（仅活动申报）：提交时设为 now + 3 天，到期自愈式流转到待审批
    voting_end_at = models.DateTimeField("投票截止时间", null=True, blank=True)

    # 审批记录
    reject_reason = models.TextField("打回/拒绝理由", blank=True, default="")
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
            ("approve_proposal", "可审批申报"),
            ("view_feedback", "可查看意见反馈/举报"),
        ]

    def __str__(self):
        return f"{self.get_proposal_type_display()}: {self.title}"


class Vote(models.Model):
    """投票记录（仅活动申报）"""

    VOTE_CHOICES = [
        ("approve", "赞成"),
        ("oppose", "反对"),
        ("abstain", "弃权"),
    ]

    proposal = models.ForeignKey(
        Proposal, on_delete=models.CASCADE,
        related_name="votes", verbose_name="申报",
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="cast_votes", verbose_name="投票人",
    )
    vote_choice = models.CharField("选项", max_length=10, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "投票"
        verbose_name_plural = "投票"
        unique_together = ["proposal", "voter"]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.voter.username} -> {self.proposal.title} ({self.get_vote_choice_display()})"


class ProposalAttachment(models.Model):
    """申报附件"""

    FILE_TYPE_CHOICES = [
        ("image", "图片"),
        ("video", "视频"),
        ("document", "文档"),
        ("archive", "压缩包"),
        ("other", "其他"),
    ]

    proposal = models.ForeignKey(
        Proposal, on_delete=models.CASCADE,
        related_name="attachments", verbose_name="申报",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="uploaded_proposal_attachments", verbose_name="上传者",
    )
    file = models.FileField("文件", upload_to=proposal_attachment_upload_path)
    file_type = models.CharField("文件类型", max_length=20, choices=FILE_TYPE_CHOICES)
    file_name = models.CharField("文件名", max_length=255)
    file_size = models.BigIntegerField("文件大小")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "申报附件"
        verbose_name_plural = "申报附件"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.file_name
