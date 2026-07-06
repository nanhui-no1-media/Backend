from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProposalViewSet

router = DefaultRouter()
router.register(r"proposals", ProposalViewSet, basename="proposal")

urlpatterns = [
    path("", include(router.urls)),
]
