from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """会话：任务讨论或私人对话"""

    TYPE_CHOICES = [
        ("task", "任务讨论"),
        ("private", "私人对话"),
        ("proposal", "申报讨论"),
    ]

    conversation_type = models.CharField("类型", max_length=10, choices=TYPE_CHOICES)
    task = models.ForeignKey(
        "tasks.Task", on_delete=models.CASCADE,
        null=True, blank=True, related_name="conversations", verbose_name="关联任务",
    )
    proposal = models.ForeignKey(
        "proposals.Proposal", on_delete=models.CASCADE,
        null=True, blank=True, related_name="conversations", verbose_name="关联申报",
    )
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
        if self.conversation_type == "task" and self.task:
            return f"任务讨论: {self.task.title}"
        if self.conversation_type == "proposal" and self.proposal:
            return f"申报讨论: {self.proposal.title}"
        return f"私人会话 ({self.pk})"


class Message(models.Model):
    """消息"""

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
