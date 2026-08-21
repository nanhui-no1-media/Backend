from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ExamData
from .permissions import CanManageExam
from .serializers import ExamDataSerializer


class ExamDataViewSet(viewsets.ModelViewSet):
    """考试看板：公开读最新/列表；写需 exam_board.add_examdata。"""

    serializer_class = ExamDataSerializer
    permission_classes = [CanManageExam]
    queryset = ExamData.objects.all()
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=["get"])
    def latest(self, request):
        exam = self.get_queryset().first()
        if exam is None:
            return Response({"status": "success", "data": None, "message": "数据库中暂无考试数据"})
        return Response({"status": "success", "data": self.get_serializer(exam).data})
