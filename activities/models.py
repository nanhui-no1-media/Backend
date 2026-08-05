"""活动模型（ADR 0007）：活动独立于申报，分众议（投票）/ 征集（收作品）两类型。

与申报(proposals)分离——申报退化为纯反馈容器。状态机与守卫集中在 lifecycle.py
（遵循 ADR 0003），此处只给 DB 枚举与字段。
"""
from django.conf import settings
from django.db import models


class Activity(models.Model):
    """活动：发起人对全社团开放的协作事项，两类型之一。"""

    TYPE_CHOICES = [
        ("deliberation", "众议"),
        ("collection", "征集"),
    ]
    # 状态语义随类型而异（状态机见 lifecycle.py）：
    #   众议：open（投票中）→ closed（已截止结算）
    #   征集：collecting（收件中）→ reviewing（复审中）→ archived（已归档）
    STATUS_CHOICES = [
        ("open", "进行中"),
        ("closed", "已结束"),
        ("collecting", "收件中"),
        ("reviewing", "复审中"),
        ("archived", "已归档"),
    ]

    type = models.CharField("类型", max_length=12, choices=TYPE_CHOICES)
    status = models.CharField("状态", max_length=12, choices=STATUS_CHOICES)
    title = models.CharField("标题", max_length=200)
    body = models.TextField("正文（HTML）", blank=True, default="")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_activities", verbose_name="发起人",
    )

    # 窗口截止时间：众议=投票截止、征集=收件截止。到点由 lifecycle 惰性流转。
    end_at = models.DateTimeField("截止时间", null=True, blank=True)

    # 众议专属：每人最多选几项（K）；K=1 即一人一票。征集忽略此字段。
    max_choices_per_voter = models.PositiveIntegerField("每人最多选几项", default=1)

    # 众议专属：秘密投票（默认公开）。秘密下仅聚合计数可见，个人明细仅超管可见。
    is_secret_ballot = models.BooleanField("秘密投票", default=False)

    # 征集专属配置（提交时校验）：
    #   allowed_extensions 空=不限（除全局禁用后缀）；逗号分隔，如 ".jpg,.png,.pdf"
    #   max_file_size null=用全局 50MB 同步上限
    #   max_files_per_submission 单个作品的文件数上限
    #   max_submissions null=不限（设了则满额自动 collecting→reviewing）
    allowed_extensions = models.TextField("允许后缀（逗号分隔）", blank=True, default="")
    max_file_size = models.BigIntegerField("单文件大小上限（字节）", null=True, blank=True)
    max_files_per_submission = models.PositiveIntegerField("单作品文件数上限", default=5)
    max_submissions = models.PositiveIntegerField("最大征集数量", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "活动"
        verbose_name_plural = "活动"
        ordering = ["-created_at"]
        permissions = [
            ("review_collection", "可复审征集作品"),
        ]

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}" # type: ignore


class VoteOption(models.Model):
    """众议的投票选项（发起人创建时定义，开放即锁定）。"""

    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE,
        related_name="options", verbose_name="活动",
    )
    text = models.CharField("选项文本", max_length=200)
    order = models.PositiveIntegerField("顺序", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "投票选项"
        verbose_name_plural = "投票选项"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.activity_id}:{self.text}" # type: ignore


class Ballot(models.Model):
    """一名成员在一次众议中的选票（一人一张，一经投出不可改）。

    具体选择（选了哪些选项）见 BallotSelection。秘密投票下 voter 仅超管可见
    （序列化层裁剪），DB 仍记录以强制一人一张 + 防重复。
    """

    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE,
        related_name="ballots", verbose_name="活动",
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="activity_ballots", verbose_name="投票人",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "选票"
        verbose_name_plural = "选票"
        unique_together = ["activity", "voter"]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.voter_id} -> {self.activity_id}" # type: ignore


class BallotSelection(models.Model):
    """选票上勾选的一个选项（每选项每张选票最多一次）。"""

    ballot = models.ForeignKey(
        Ballot, on_delete=models.CASCADE,
        related_name="selections", verbose_name="选票",
    )
    option = models.ForeignKey(
        VoteOption, on_delete=models.CASCADE,
        related_name="selections", verbose_name="选项",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "投票选择"
        verbose_name_plural = "投票选择"
        unique_together = ["ballot", "option"]

    def __str__(self):
        return f"{self.ballot_id}:{self.option_id}" # type: ignore


class Submission(models.Model):
    """征集作品：一名成员在一次征集中提交的实体（一束文件）。

    一人一作品（unique [activity, submitter]）；提交即锁定（提交者不可改/撤）。
    文件复用统一附件系统（attachments.Attachment.submission 父级）。复审见 T5。
    """

    REVIEW_CHOICES = [
        ("pending", "待复审"),
        ("accepted", "录用"),
        ("rejected", "退稿"),
    ]

    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE,
        related_name="submissions", verbose_name="活动",
    )
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="activity_submissions", verbose_name="提交者",
    )
    review_status = models.CharField(
        "复审状态", max_length=10, choices=REVIEW_CHOICES, default="pending",
    )
    review_comment = models.TextField("复审评语", blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_submissions", verbose_name="复审人",
    )
    reviewed_at = models.DateTimeField("复审时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "作品"
        verbose_name_plural = "作品"
        unique_together = ["activity", "submitter"]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.submitter_id} -> {self.activity_id} ({self.review_status})" # type: ignore
