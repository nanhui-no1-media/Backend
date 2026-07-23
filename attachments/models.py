"""统一附件模型。

一张表可挂在任务或申报上（两个可空外键，CASCADE），用 DB CheckConstraint
强制「恰好一个父级」。删除父级时 CASCADE 连带删除附件行，再由 post_delete
信号（见 signals.py）同步删除磁盘文件——自动回收，无需定时任务。

注：本券（T1）刻意使用临时反向访问器名 ``unified_attachments`` /
``uploaded_unified_attachments``，避免与旧模型 ``tasks.Attachment`` /
``proposals.ProposalAttachment`` 的 ``attachments`` 访问器冲突；待 T3 移除旧模型
后，再规范化为 ``attachments``（纯代码改动，不产生迁移）。
"""
import os
import uuid

from django.conf import settings
from django.db import models


def attachment_upload_path(instance, filename):
    """扁平存储：attachments/<uuid>.<ext>（不再按父级分目录）。"""
    ext = os.path.splitext(filename)[1]
    return f"attachments/{uuid.uuid4().hex}{ext}"


class Attachment(models.Model):
    """统一附件：恰好挂在一个父级（任务或申报）上。"""

    FILE_TYPE_CHOICES = [
        ("image", "图片"),
        ("video", "视频"),
        ("document", "文档"),
        ("archive", "压缩包"),
        ("other", "其他"),
    ]

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="uploaded_unified_attachments", verbose_name="上传者",
    )
    task = models.ForeignKey(
        "tasks.Task", on_delete=models.CASCADE,
        null=True, blank=True, related_name="unified_attachments", verbose_name="任务",
    )
    proposal = models.ForeignKey(
        "proposals.Proposal", on_delete=models.CASCADE,
        null=True, blank=True, related_name="unified_attachments", verbose_name="申报",
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
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(task__isnull=True, proposal__isnull=False)
                    | models.Q(task__isnull=False, proposal__isnull=True)
                ),
                name="attachment_exactly_one_parent",
                violation_error_message="附件必须且只能挂在一个父级（任务或申报）上。",
            ),
        ]

    def __str__(self):
        return self.file_name
