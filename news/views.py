from django.db.models import F
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from tasks.models import Tag

from .models import News
from .permissions import CanManageNews
from .serializers import NewsDetailSerializer, NewsListSerializer, NewsTagSerializer

# 公开（匿名可访问）的 action
PUBLIC_ACTIONS = frozenset({"list", "retrieve", "featured", "hot", "tags"})


class NewsViewSet(viewsets.ModelViewSet):
    """新闻：公开读（已发布），「信息组」/ 超管可写。"""

    filterset_fields = ["category", "featured", "is_published"]
    search_fields = ["title", "summary", "content"]
    ordering_fields = ["published_at", "views", "created_at"]
    ordering = ["-published_at"]

    def get_queryset(self):
        qs = News.objects.select_related("author", "author__profile").prefetch_related("tags")
        # 公开读只返回已发布；写操作（信息组）可见全部
        if self.action in PUBLIC_ACTIONS:
            qs = qs.filter(is_published=True)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return NewsListSerializer
        return NewsDetailSerializer

    def get_permissions(self):
        if self.action in PUBLIC_ACTIONS:
            return [AllowAny()]
        return [IsAuthenticated(), CanManageNews()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # 阅读量 +1（F 表达式避免并发竞态）
        News.objects.filter(pk=instance.pk).update(views=F("views") + 1)
        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def featured(self, request):
        """头条：最近一条 featured 已发布新闻；无则最近一条。"""
        qs = self.get_queryset()
        item = qs.filter(featured=True).first() or qs.first()
        if item is None:
            return Response(None)
        return Response(NewsListSerializer(item, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def hot(self, request):
        """热门阅读：按阅读量前 5。"""
        qs = self.get_queryset().order_by("-views", "-published_at")[:5]
        return Response(NewsListSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def tags(self, request):
        """标签云：仅返回被新闻引用过的标签，附新闻数。"""
        qs = Tag.objects.filter(news__isnull=False).distinct()
        return Response(NewsTagSerializer(qs, many=True, context={"request": request}).data)
