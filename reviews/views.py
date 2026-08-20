from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .lifecycle import APPROVE, REJECT, REMOVE, TransitionDenied, apply
from .models import Review
from .permissions import CanModerateReview
from .serializers import ReviewSerializer


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """统一审核队列：列出待审项，对新闻/活动执行通过、驳回、下架。"""

    serializer_class = ReviewSerializer
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "reviewed_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Review.objects.select_related(
            "news", "activity",
            "reviewer", "reviewer__profile",
        )

    def get_permissions(self):
        return [IsAuthenticated(), CanModerateReview()]

    def _transition(self, request, action, *, comment=""):
        review = self.get_object()
        try:
            apply(action, review, request.user, comment=comment)
        except TransitionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReviewSerializer(review, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._transition(request, APPROVE, comment=request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._transition(request, REJECT, comment=request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def remove(self, request, pk=None):
        return self._transition(request, REMOVE, comment=request.data.get("comment", ""))
