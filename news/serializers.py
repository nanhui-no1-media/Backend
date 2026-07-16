import bleach
from django.utils import timezone
from rest_framework import serializers

from tasks.models import Tag
from tasks.serializers import SimpleUserSerializer

from .models import News

# 正文 HTML 白名单：与前端 RichTextEditor（TipTap：StarterKit + TaskList + Table + Image）输出对齐。
# 服务端清洗可挡住信息组成员绕过编辑器、直接经 API 注入的 <script>/事件处理器/javascript: 等。
_NEWS_ALLOWED_TAGS = [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "s", "del", "u", "mark", "code", "sub", "sup",
    "pre", "blockquote",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "figure", "figcaption", "span",
]
_NEWS_ALLOWED_ATTRS = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "th": ["colspan", "rowspan", "colwidth"],
    "td": ["colspan", "rowspan", "colwidth"],
    "ul": ["class", "data-type"],
    "ol": ["class", "data-type"],
    "li": ["class", "data-type", "data-checked"],
}
_NEWS_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]

# 封面图上限：与头像一致（见 accounts.views.profile_update_view）
_COVER_MAX_SIZE = 2 * 1024 * 1024
_COVER_ALLOWED_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")


def _sanitize_content(html: str) -> str:
    """清洗正文 HTML：仅保留白名单标签/属性/协议，其余剥离（strip=True，内容保留）。"""
    if not html:
        return html
    return bleach.clean(
        html,
        tags=_NEWS_ALLOWED_TAGS,
        attributes=_NEWS_ALLOWED_ATTRS,
        protocols=_NEWS_ALLOWED_PROTOCOLS,
        strip=True,
    )


def _absolute_cover_url(obj, request):
    if obj.cover_image and hasattr(obj.cover_image, "url"):
        url = obj.cover_image.url
        return request.build_absolute_uri(url) if request else url
    return None


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

    class Meta:
        model = News
        fields = [
            "id", "title", "category", "summary", "cover_image_url",
            "author", "tags", "featured", "views", "is_published",
            "published_at", "created_at",
        ]

    def get_cover_image_url(self, obj):
        return _absolute_cover_url(obj, self.context.get("request"))


class NewsDetailSerializer(serializers.ModelSerializer):
    """详情序列化：含正文、相关阅读；写入接受封面文件与 tag_ids。"""

    author = SimpleUserSerializer(read_only=True)
    tags = NewsTagSerializer(many=True, read_only=True)
    cover_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    cover_image_url = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()

    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False, write_only=True, source="tags",
    )

    class Meta:
        model = News
        fields = [
            "id", "title", "category", "summary", "content",
            "cover_image", "cover_image_url",
            "author", "tags", "tag_ids",
            "featured", "views", "is_published", "published_at",
            "related", "created_at", "updated_at",
        ]
        read_only_fields = ["author", "views", "published_at", "created_at", "updated_at"]

    def get_cover_image_url(self, obj):
        return _absolute_cover_url(obj, self.context.get("request"))

    def get_related(self, obj):
        """同分类、已发布、最新 3 条（排除自身）。"""
        qs = (
            News.objects.filter(is_published=True, category=obj.category)
            .exclude(pk=obj.pk)
            .select_related("author", "author__profile")
            .prefetch_related("tags")
            .order_by("-published_at", "-created_at")[:3]
        )
        return NewsListSerializer(qs, many=True, context=self.context).data

    def validate_content(self, value):
        # 服务端清洗：防止绕过编辑器注入恶意 HTML（XSS）
        return _sanitize_content(value or "")

    def validate_cover_image(self, value):
        # 与头像校验一致：限制大小与类型（客户端 2MB 检查可被直接 API 调用绕过）
        if value:
            if getattr(value, "size", 0) > _COVER_MAX_SIZE:
                raise serializers.ValidationError("封面图不能超过 2MB。")
            if getattr(value, "content_type", "") not in _COVER_ALLOWED_TYPES:
                raise serializers.ValidationError("封面仅支持 JPG、PNG、GIF、WebP 格式。")
        return value

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        # 默认发布：补发布时间
        if validated_data.get("is_published", True) and not validated_data.get("published_at"):
            validated_data["published_at"] = timezone.now()
        news = News.objects.create(**validated_data)
        if tags:
            news.tags.set(tags)
        return news

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        # 替换封面时删除旧文件，避免孤儿文件堆积
        new_cover = validated_data.get("cover_image")
        if new_cover and instance.cover_image and instance.cover_image.name != getattr(new_cover, "name", None):
            instance.cover_image.delete(save=False)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # 由未发布转为发布时补发布时间
        if validated_data.get("is_published") and not instance.published_at:
            instance.published_at = timezone.now()
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance
