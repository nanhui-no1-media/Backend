from django.db.models import Count, Prefetch
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .clock import clock_payload
from .models import Exam, ExamBatch, ExamErrata, ExamSubject
from .permissions import CanManageExam
from .push import broadcast
from .serializers import (
    ExamErrataSerializer,
    ExamListSerializer,
    ExamSerializer,
)


def _exam_queryset():
    return Exam.objects.prefetch_related(
        Prefetch(
            "batches",
            queryset=ExamBatch.objects.prefetch_related(
                Prefetch("subjects", queryset=ExamSubject.objects.all()),
            ),
        ),
    )


class ExamViewSet(viewsets.ModelViewSet):
    """考试看板：公开读列表/详情/最新/授时；写需 exam_board.add_exam。"""

    permission_classes = [CanManageExam]
    queryset = Exam.objects.all()
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        if self.action == "list":
            return Exam.objects.annotate(batch_count=Count("batches", distinct=True)).order_by("-id")
        return _exam_queryset()

    def get_serializer_class(self):
        if self.action == "list":
            return ExamListSerializer
        return ExamSerializer

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)
        broadcast("exam", {"exam_id": serializer.instance.pk})

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        broadcast("exam", {"exam_id": serializer.instance.pk})

    def perform_destroy(self, instance):
        exam_id = instance.pk
        instance.delete()
        broadcast("exam", {"exam_id": exam_id})

    @action(detail=False, methods=["get"])
    def latest(self, request):
        exam = self.get_queryset().first()
        if exam is None:
            return Response({"status": "success", "data": None, "message": "数据库中暂无考试数据"})
        return Response({"status": "success", "data": ExamSerializer(exam, context={"request": request}).data})

    @action(detail=False, methods=["get"])
    def clock(self, request):
        return Response(clock_payload())


class ExamErrataViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """题目误刊：公开读当前一条；写需 exam_board.add_exam。"""

    permission_classes = [CanManageExam]
    serializer_class = ExamErrataSerializer
    queryset = ExamErrata.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @action(detail=False, methods=["get"])
    def current(self, request):
        item = ExamErrata.objects.filter(dismissed_at__isnull=True).first()
        if item is None:
            return Response({"status": "success", "data": None})
        return Response({"status": "success", "data": self.get_serializer(item).data})

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ExamErrata.objects.filter(dismissed_at__isnull=True).update(dismissed_at=timezone.now())
        item = serializer.save(created_by=request.user)
        payload = ExamErrataSerializer(item, context={"request": request}).data
        broadcast("errata", payload)
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def dismiss(self, request):
        updated = ExamErrata.objects.filter(dismissed_at__isnull=True).update(
            dismissed_at=timezone.now(),
        )
        if updated:
            broadcast("errata_cleared", {})
        return Response({"status": "success", "dismissed": updated})
