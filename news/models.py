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
    views = models.PositiveIntegerField("阅读人数", default=0)
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


class NewsView(models.Model):
    """单条新闻的去重阅读记录。

    reader_key 统一登录 / 匿名两种情况：登录用户 = ``"user:{pk}"``，
    匿名 = ``"ip:{sha256(REMOTE_ADDR)}"``（存 hash 不存明文 IP）。
    ``News.views`` 是去重后的累计读者数缓存。
    """

    news = models.ForeignKey(
        News, on_delete=models.CASCADE, related_name="view_records",
        verbose_name="新闻",
    )
    reader_key = models.CharField("读者标识", max_length=80)
    viewed_at = models.DateTimeField("阅读时间", auto_now_add=True)

    class Meta:
        verbose_name = "阅读记录"
        verbose_name_plural = "阅读记录"
        unique_together = ["news", "reader_key"]

    def __str__(self):
        return f"{self.news_id}:{self.reader_key}"
