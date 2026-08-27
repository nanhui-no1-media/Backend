from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BannerViewSet,
    CommentThreadViewSet,
    CommentViewSet,
    ConversationViewSet,
    MuteViewSet,
    NotificationViewSet,
)

router = DefaultRouter()
router.register(r"threads", CommentThreadViewSet, basename="comment-thread")
router.register(r"comments", CommentViewSet, basename="comment")
router.register(r"conversations", ConversationViewSet, basename="conversation")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"mutes", MuteViewSet, basename="mute")
router.register(r"banners", BannerViewSet, basename="banner")

urlpatterns = [
    path("", include(router.urls)),
]
