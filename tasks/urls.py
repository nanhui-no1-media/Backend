from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AttachmentViewSet, TagViewSet, TaskViewSet

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"attachments", AttachmentViewSet, basename="attachment")

urlpatterns = [
    path("", include(router.urls)),
]
