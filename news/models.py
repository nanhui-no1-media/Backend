import os
import uuid

from django.conf import settings
from django.db import models


def cover_upload_path(instance, filename):
    """新闻封面图：统一存到 news_covers/，文件名用 uuid 防冲突。"""
    ext = os.path.splitext(filename)[1]
    return f"news_covers/{uuid.uuid4().hex}{ext}"


class News(models.Model):
    """新闻 / 公告（社团公告、活动回顾、作品展示、通知）。"""

    CATEGORY_CHOICES = [
        ("notice", "社团公告"),
        ("recap", "活动回顾"),
        ("work", "作品展示"),
        ("inform", "通知"),
    ]

    title = models.CharField("标题", max_length=200)
    category = models.CharField("分类", max_length=20, choices=CATEGORY_CHOICES, default="notice")
    summary = models.CharField("摘要", max_length=280, blank=True, default="")
    content = models.TextField("正文（HTML）", blank=True, default="")
    cover_image = models.ImageField("封面图", upload_to=cover_upload_path, blank=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="news", verbose_name="作者",
    )
    tags = models.ManyToManyField(
        "tasks.Tag", blank=True, related_name="news", verbose_name="标签",
    )

    featured = models.BooleanField("头条", default=False)
    views = models.PositiveIntegerField("阅读量", default=0)
    is_published = models.BooleanField("已发布", default=True)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "新闻"
        verbose_name_plural = "新闻"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title
