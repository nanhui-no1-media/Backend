import os

from django.utils import timezone
from rest_framework import serializers

from common.rich_text import sanitize_html
from reviews.visibility import comment_for, public_q, status_of
from tasks.models import Tag
from tasks.serializers import CommentThreadHostMixin, SimpleUserSerializer

from .models import News
from .thumbnails import make_cover_thumbnail
from attachments.models import Attachment
from attachments.serializers import AttachmentSerializer

# 正文 HTML 清洗：复用共享净化器 common.rich_text.sanitize_html（见 validate_content）。
# iframe 策略与全站一致（任意 https + 服务端盖 sandbox；详见 common/rich_text.py）。

# 封面图上限：5MB（与正文内嵌图一致；头像仍为 2MB，见 accounts.views.profile_update_view）
_COVER_MAX_SIZE = 5 * 1024 * 1024
_COVER_ALLOWED_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")


def _absolute_file_url(file_field, request):
    if file_field and hasattr(file_field, "url"):
        url = file_field.url
        return request.build_absolute_uri(url) if request else url
    return None


def _absolute_cover_url(obj, request):
    return _absolute_file_url(obj.cover_image, request)


def _absolute_thumbnail_url(obj, request):
    """列表 / 卡片用缩略图；无缩略图（旧图 / 生成失败）回退原图。"""
    if not obj.cover_image:
        return None
    return _absolute_file_url(obj.cover_thumbnail, request) or _absolute_cover_url(obj, request)


class NewsTagSerializer(serializers.ModelSerializer):
    """新闻标签（带新闻数）。复用 tasks.Tag，但按新闻维度计数。"""

    news_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["id", "name", "color", "news_count"]

    def get_news_count(self, obj):
        return obj.news.count()


class NewsListSerializer(serializers.ModelSerializer):
    """列表用精简序列化（不含正文）。"""

    author = SimpleUserSerializer(read_only=True)
    tags = NewsTagSerializer(many=True, read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    cover_thumbnail_url = serializers.SerializerMethodField()
    review_status = serializers.SerializerMethodField()

    class Meta:
        model = News
        fields = [
            "id", "title", "summary", "cover_image_url", "cover_thumbnail_url",
            "author", "tags", "featured", "views", "is_published",
            "review_status", "published_at", "created_at",
        ]

    def get_review_status(self, obj):
        return status_of(obj)

    def get_cover_image_url(self, obj):
        return _absolute_cover_url(obj, self.context.get("request"))

    def get_cover_thumbnail_url(self, obj):
        return _absolute_thumbnail_url(obj, self.context.get("request"))


class NewsAttachmentSerializer(AttachmentSerializer):
    """新闻详情用的精简附件视图：不含 uploaded_by（详情匿名可读）。复用父类 get_file_url。"""

    class Meta:
        model = Attachment
        fields = ["id", "file_url", "file_type", "file_name", "file_size"]


class NewsDetailSerializer(CommentThreadHostMixin, serializers.ModelSerializer):
    """详情序列化：含正文、相关阅读；写入接受封面文件与 tag_ids。"""

    author = SimpleUserSerializer(read_only=True)
    tags = NewsTagSerializer(many=True, read_only=True)
    cover_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    cover_image_url = serializers.SerializerMethodField()
    cover_thumbnail_url = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()
    attachments = NewsAttachmentSerializer(many=True, read_only=True)
    review_status = serializers.SerializerMethodField()
    review_comment = serializers.SerializerMethodField()

    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False, write_only=True, source="tags",
    )

    class Meta:
        model = News
        fields = [
            "id", "title", "summary", "content",
            "cover_image", "cover_image_url", "cover_thumbnail_url",
            "author", "tags", "tag_ids",
            "featured", "views", "is_published", "review_status", "review_comment", "published_at",
            "related", "created_at", "updated_at", "attachments",
            "comment_thread", "comment_thread_status",
        ]
        read_only_fields = ["author", "views", "published_at", "created_at", "updated_at"]

    def get_cover_image_url(self, obj):
        return _absolute_cover_url(obj, self.context.get("request"))

    def get_cover_thumbnail_url(self, obj):
        return _absolute_thumbnail_url(obj, self.context.get("request"))

    def get_review_status(self, obj):
        return status_of(obj)

    def get_review_comment(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return comment_for(obj, user)

    def get_related(self, obj):
        """已发布且过审、按发布时间最新 3 条（排除自身）。"""
        qs = (
            News.objects.filter(public_q("news"), is_published=True)
            .exclude(pk=obj.pk)
            .select_related("author", "author__profile")
            .prefetch_related("tags")
            .order_by("-published_at", "-created_at")[:3]
        )
        return NewsListSerializer(qs, many=True, context=self.context).data

    def validate_content(self, value):
        # 服务端清洗：防止绕过编辑器注入恶意 HTML（XSS）
        return sanitize_html(value or "")

    def validate_cover_image(self, value):
        # 大小与类型双校验（客户端 5MB 检查可被直接 API 调用绕过）
        if value:
            if getattr(value, "size", 0) > _COVER_MAX_SIZE:
                raise serializers.ValidationError("封面图不能超过 5MB。")
            if getattr(value, "content_type", "") not in _COVER_ALLOWED_TYPES:
                raise serializers.ValidationError("封面仅支持 JPG、PNG、GIF、WebP 格式。")
        return value

    def _sync_cover_thumbnail(self, news):
        """封面存在则（重新）生成缩略图；失败静默（列表回退原图）。"""
        if not news.cover_image:
            return
        content = make_cover_thumbnail(news.cover_image)
        if content is None:
            return
        if news.cover_thumbnail:
            news.cover_thumbnail.delete(save=False)
        base = os.path.splitext(os.path.basename(news.cover_image.name))[0]
        news.cover_thumbnail.save(f"{base}.jpg", content, save=True)

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        # 默认发布：补发布时间
        if validated_data.get("is_published", True) and not validated_data.get("published_at"):
            validated_data["published_at"] = timezone.now()
        news = News.objects.create(**validated_data)
        if tags:
            news.tags.set(tags)
        self._sync_cover_thumbnail(news)
        return self.apply_comment_thread_status(news)

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        cover_changed = "cover_image" in validated_data
        # 替换封面时删除旧文件（含缩略图），避免孤儿文件堆积
        new_cover = validated_data.get("cover_image")
        if new_cover and instance.cover_image and instance.cover_image.name != getattr(new_cover, "name", None):
            instance.cover_image.delete(save=False)
            if instance.cover_thumbnail:
                instance.cover_thumbnail.delete(save=False)
        elif cover_changed and not new_cover and instance.cover_thumbnail:
            # 封面被清空：缩略图一并清
            instance.cover_thumbnail.delete(save=False)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # 由未发布转为发布时补发布时间
        if validated_data.get("is_published") and not instance.published_at:
            instance.published_at = timezone.now()
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        # 换过封面则重新生成；旧数据缺缩略图时顺手补上
        if cover_changed or (instance.cover_image and not instance.cover_thumbnail):
            self._sync_cover_thumbnail(instance)
        return self.apply_comment_thread_status(instance)
