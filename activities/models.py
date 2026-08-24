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
        ("exhibition", "展示"),
    ]
    # 状态语义随类型而异（状态机见 lifecycle.py）：
    #   排期：scheduled（待开始，start_at 之前）→ 到点开放
    #   众议：open（投票中）→ closed（已截止结算）
    #   征集：collecting（收件中）→ reviewing（复审中）→ archived（已归档）
    STATUS_CHOICES = [
        ("scheduled", "待开始"),
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

    # 开始时间（可选）：设了未来时间则创建后处于 scheduled，到点自动开放；不填则创建即开放。
    start_at = models.DateTimeField("开始时间", null=True, blank=True)
    # 窗口截止时间：众议=投票截止、征集=收件截止。到点由 lifecycle 惰性流转。
    end_at = models.DateTimeField("截止时间", null=True, blank=True)

    # 众议专属：每人最多选几项（K）；K=1 即一人一票。征集忽略此字段。
    max_choices_per_voter = models.PositiveIntegerField("每人最多选几项", default=1)

    # 众议专属：秘密投票（默认公开）。秘密下仅聚合计数可见，个人明细仅超管可见。
    is_secret_ballot = models.BooleanField("秘密投票", default=False)

    # 征集专属配置（提交时校验）：
    #   allowed_extensions 空=不限（除全局禁用后缀）；逗号分隔，如 ".jpg,.png,.pdf"
    #   max_file_size null=用站点策略同步上传上限
    #   max_files_per_submission 单个作品的文件数上限
    #   max_submissions null=不限（设了则满额自动 collecting→reviewing）
    allowed_extensions = models.TextField("允许后缀（逗号分隔）", blank=True, default="")
    max_file_size = models.BigIntegerField("单文件大小上限（字节）", null=True, blank=True)
    max_files_per_submission = models.PositiveIntegerField("单作品文件数上限", default=5)
    max_submissions = models.PositiveIntegerField("最大征集数量", null=True, blank=True)

    # 征集专属：是否需要复审。True（默认）= 收集→复审→归档，仅录用作品公开；
    # False = 收集→归档（跳过复审），作品提交即公开。
    review_enabled = models.BooleanField("需要复审", default=True)

    # 展示专属：是否启用活动级投票（复用众议机制：每展品一选项 + 1..K）。
    # True = 创建时为每展品建 VoteOption，成员可对展品投票；False（默认）= 纯陈列，
    # 不建选项，仅赞/踩（ExhibitRating）。创建后不可改。
    voting_enabled = models.BooleanField("启用投票", default=False)

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


class Exhibit(models.Model):
    """展品：展示活动里的一个陈列单元（一束文件），创建时录入并冻结。

    每个展品同时是一个投票选项（``vote_option`` 一对一指向众议的 VoteOption），
    故成员可对展品投票（1..K）。赞/踩见 ExhibitRating。文件复用统一附件系统
    （attachments.Attachment.exhibit 父级）。
    """

    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE,
        related_name="exhibits", verbose_name="所属展示",
    )
    title = models.CharField("标题", max_length=200, blank=True, default="")
    # 展品即选项：创建时与一个 VoteOption 一对一绑定，投票计数走该 option。
    vote_option = models.OneToOneField(
        VoteOption, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="exhibit", verbose_name="对应投票选项",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "展品"
        verbose_name_plural = "展品"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.activity_id}:{self.title or self.id}" # type: ignore


class ExhibitRating(models.Model):
    """展品评分：一名成员对一个展品的赞/踩。三态（none/like/dislike）靠「无行=none」表达。

    唯一 [exhibit, user]：每人每展品一条。互斥（一行只记 like 或 dislike）；可改（翻转 choice）；
    可撤（再点当前态 = 删行 = none）。
    """

    RATING_CHOICES = [
        ("like", "赞"),
        ("dislike", "踩"),
    ]

    exhibit = models.ForeignKey(
        Exhibit, on_delete=models.CASCADE,
        related_name="ratings", verbose_name="展品",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="exhibit_ratings", verbose_name="评分人",
    )
    choice = models.CharField("选择", max_length=8, choices=RATING_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "展品评分"
        verbose_name_plural = "展品评分"
        unique_together = ["exhibit", "user"]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user_id} -> {self.exhibit_id} ({self.choice})" # type: ignore
