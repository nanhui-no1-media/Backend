from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """1:1 私人对话。任务/申报讨论已拆到 CommentThread / Notification。"""

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="conversations", verbose_name="参与者",
    )
    title = models.CharField("标题", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "会话"
        verbose_name_plural = "会话"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"私人会话 ({self.pk})"


class Message(models.Model):
    """私信消息。"""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name="messages", verbose_name="会话",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="sent_messages", verbose_name="发送者",
    )
    content = models.TextField("内容")
    mentions = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name="mentioned_in_messages", verbose_name="提及用户",
    )
    retracted_at = models.DateTimeField("撤回时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "消息"
        verbose_name_plural = "消息"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender.username}: {self.content[:30]}"


class MessageReadStatus(models.Model):
    """消息已读状态"""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE,
        related_name="read_statuses", verbose_name="消息",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="message_read_statuses", verbose_name="用户",
    )
    read_at = models.DateTimeField("已读时间", auto_now_add=True)

    class Meta:
        verbose_name = "已读状态"
        verbose_name_plural = "已读状态"
        unique_together = ["message", "user"]

    def __str__(self):
        return f"{self.user.username} read message {self.message_id}"


def unread_message_count(user, conversation=None):
    """该用户尚未读的消息数。

    - 只统计该用户参与的会话（``conversation=None`` 时为全部，否则限定单个会话）；
    - 不计自己发出的消息——发送者不会为自己生成 MessageReadStatus，
      若不排除，凡是发过消息的人未读数永远 ≥1（顶栏红点会常亮）。

    供顶栏铃铛红点（总数）与会话列表未读徽标（单会话）共用。
    """
    qs = (
        Message.objects
        .filter(conversation__participants=user, retracted_at__isnull=True)
        .exclude(sender=user)
    )
    if conversation is not None:
        qs = qs.filter(conversation=conversation)
    return qs.exclude(read_statuses__user=user).count()


class CommentThread(models.Model):
    """宿主评论区：恰好挂在一条新闻 / 活动 / 任务上。"""

    STATUS_OPEN = "open"
    STATUS_MUTED = "muted"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "开放"),
        (STATUS_MUTED, "禁言"),
        (STATUS_CLOSED, "关闭"),
    ]

    news = models.OneToOneField(
        "news.News", on_delete=models.CASCADE,
        null=True, blank=True, related_name="comment_thread", verbose_name="新闻",
    )
    activity = models.OneToOneField(
        "activities.Activity", on_delete=models.CASCADE,
        null=True, blank=True, related_name="comment_thread", verbose_name="活动",
    )
    task = models.OneToOneField(
        "tasks.Task", on_delete=models.CASCADE,
        null=True, blank=True, related_name="comment_thread", verbose_name="任务",
    )
    status = models.CharField(
        "状态", max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )

    class Meta:
        verbose_name = "评论区"
        verbose_name_plural = "评论区"
        permissions = [
            ("manage_comment_thread", "评论区协管"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(news__isnull=False, activity__isnull=True, task__isnull=True)
                    | models.Q(news__isnull=True, activity__isnull=False, task__isnull=True)
                    | models.Q(news__isnull=True, activity__isnull=True, task__isnull=False)
                ),
                name="commentthread_exactly_one_parent",
                violation_error_message="评论区必须且只能挂在一个宿主（新闻/活动/任务）上。",
            ),
        ]

    def __str__(self):
        if self.news_id:
            return f"评论区 · 新闻 {self.news_id}"
        if self.activity_id:
            return f"评论区 · 活动 {self.activity_id}"
        if self.task_id:
            return f"评论区 · 任务 {self.task_id}"
        return f"评论区 {self.pk}"


class Comment(models.Model):
    """评论区里的一条评论。``parent`` 为空即根评论。"""

    thread = models.ForeignKey(
        CommentThread, on_delete=models.CASCADE,
        related_name="comments", verbose_name="评论区",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="authored_comments", verbose_name="作者",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE,
        null=True, blank=True, related_name="replies", verbose_name="父评论",
    )
    content = models.TextField("内容")
    retracted_at = models.DateTimeField("撤回时间", null=True, blank=True)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="deleted_comments", verbose_name="删除人",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "评论"
        verbose_name_plural = "评论"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "parent", "created_at"]),
        ]

    def __str__(self):
        return f"{self.author.username}: {self.content[:30]}"


class Notification(models.Model):
    """站内通知（评论 / 审核 / 纪律）。不克隆私信。"""

    CATEGORY_COMMENT = "comment"
    CATEGORY_REVIEW = "review"
    CATEGORY_DISCIPLINE = "discipline"
    CATEGORY_CHOICES = [
        (CATEGORY_COMMENT, "评论"),
        (CATEGORY_REVIEW, "审核"),
        (CATEGORY_DISCIPLINE, "纪律"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications", verbose_name="接收人",
    )
    category = models.CharField("类别", max_length=20, choices=CATEGORY_CHOICES)
    event = models.CharField("事件", max_length=64)
    payload = models.JSONField("载荷", default=dict, blank=True)
    read_at = models.DateTimeField("已读时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "read_at"]),
        ]

    def __str__(self):
        return f"{self.recipient.username} · {self.category} · {self.event}"


class UserMute(models.Model):
    """全站禁言记录。当前生效 = 最新一行 ``lifted_at`` 为空且（``ends_at`` 为空或未到期）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="mutes", verbose_name="被禁言用户",
    )
    muted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="issued_mutes", verbose_name="操作人",
    )
    reason = models.TextField("理由", blank=True, default="")
    starts_at = models.DateTimeField("开始时间", default=timezone.now)
    ends_at = models.DateTimeField("结束时间", null=True, blank=True)
    lifted_at = models.DateTimeField("解除时间", null=True, blank=True)

    class Meta:
        verbose_name = "禁言"
        verbose_name_plural = "禁言"
        ordering = ["-starts_at"]
        permissions = [
            ("mute_user", "全站禁言"),
        ]
        indexes = [
            models.Index(fields=["user", "lifted_at", "ends_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} muted by {self.muted_by.username}"


class Banner(models.Model):
    """全站横幅公告。同时只展示一条：未过期中 priority 最高，并列取较新。"""

    body = models.TextField("正文")
    link = models.CharField("链接", max_length=500, blank=True, default="")
    starts_at = models.DateTimeField("开始时间")
    ends_at = models.DateTimeField("结束时间")
    priority = models.IntegerField(
        "优先级", default=0,
        help_text="数值越大越优先；相同则较新者胜出。",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "横幅公告"
        verbose_name_plural = "横幅公告"
        ordering = ["-priority", "-created_at"]
        permissions = [
            ("manage_announcement", "管理横幅公告"),
        ]

    def __str__(self):
        return self.body[:40]
