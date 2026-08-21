from django.conf import settings
from django.db import models


class ExamData(models.Model):
    """一场考试安排：日期 / 标题 / 科目列表。可多场，按日期取最新。"""

    exam_date = models.DateField("考试日期")
    exam_title = models.CharField("考试标题", max_length=50)
    exam_list = models.CharField("科目列表", max_length=255)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="exam_records", verbose_name="写入人",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "考试"
        verbose_name_plural = "考试"
        ordering = ["-exam_date", "-id"]

    def __str__(self):
        return f"{self.exam_date} {self.exam_title}"
