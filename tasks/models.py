import os
import uuid

from django.conf import settings
from django.db import models


def attachment_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"task_attachments/task_{instance.task_id}/{uuid.uuid4().hex}{ext}"


class Tag(models.Model):
    """标签"""
    name = models.CharField("名称", max_length=50, unique=True)
    color = models.CharField("颜色", max_length=7, default="#007bff")

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Task(models.Model):
    """任务"""
    STATUS_CHOICES = [
        ("pending", "待处理"),
        ("in_progress", "进行中"),
        ("reviewing", "待验收"),
        ("review", "审核中"),
        ("completed", "已完成"),
        ("cancelled", "已取消"),
    ]
    PRIORITY_CHOICES = [
        ("low", "低"),
        ("medium", "中"),
        ("high", "高"),
        ("urgent", "紧急"),
    ]

    title = models.CharField("标题", max_length=200)
    description = models.TextField("描述", blank=True)
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="pending")
    priority = models.CharField("优先级", max_length=20, choices=PRIORITY_CHOICES, default="medium")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="created_tasks", verbose_name="创建人",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_tasks", verbose_name="负责人",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="tasks", verbose_name="标签")

    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name="collaborating_tasks", verbose_name="协作者",
    )

    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    reject_reason = models.TextField("打回理由", blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "任务"
        verbose_name_plural = "任务"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class TaskClaimRequest(models.Model):
    """任务认领请求"""
    STATUS_CHOICES = [
        ("pending", "待审核"),
        ("approved", "已通过"),
        ("rejected", "已拒绝"),
    ]

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name="claim_requests", verbose_name="任务",
    )
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="claim_requests", verbose_name="申请者",
    )
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="pending")
    reason = models.TextField("申请理由", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_claims", verbose_name="审核人",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "认领请求"
        verbose_name_plural = "认领请求"
        ordering = ["-created_at"]
        unique_together = ["task", "claimant"]

    def __str__(self):
        return f"{self.claimant.username} -> {self.task.title} ({self.status})"


class Attachment(models.Model):
    """附件"""
    FILE_TYPE_CHOICES = [
        ("image", "图片"),
        ("video", "视频"),
        ("document", "文档"),
        ("archive", "压缩包"),
        ("other", "其他"),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments", verbose_name="任务")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="uploaded_attachments", verbose_name="上传者",
    )
    file = models.FileField("文件", upload_to=attachment_upload_path)
    file_type = models.CharField("文件类型", max_length=20, choices=FILE_TYPE_CHOICES)
    file_name = models.CharField("文件名", max_length=255)
    file_size = models.BigIntegerField("文件大小")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "附件"
        verbose_name_plural = "附件"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.file_name
