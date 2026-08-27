from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from about.permissions import CanEditAbout
from activities.device import device_id_from_request
from activities.models import Questionnaire, QuestionnaireResponse

from .models import RecruitmentNotice
from .serializers import (
    JoinQuestionnaireSerializer,
    JoinResponseSerializer,
    RecruitmentNoticeSerializer,
)


class IsAboutEditor(BasePermission):
    """招生作答列表等敏感读：必须持 about.change_aboutpage。"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("about.change_aboutpage"))


def _already_responded(questionnaire, request):
    user = request.user if request.user.is_authenticated else None
    if user is not None:
        return questionnaire.responses.filter(user=user).exists()
    device_id = device_id_from_request(request)
    if not device_id:
        return False
    return questionnaire.responses.filter(user__isnull=True, device_id=device_id).exists()


class RecruitmentLandingView(APIView):
    """GET /recruitment/：公告 + 问卷 Schema，公开可读。"""

    permission_classes = [AllowAny]

    def get(self, request):
        notice = RecruitmentNotice.objects.get_solo()
        questionnaire = Questionnaire.get_join()
        return Response({
            "notice": RecruitmentNoticeSerializer(notice).data,
            "schema": questionnaire.schema,
            "already_responded": _already_responded(questionnaire, request),
        })


class RecruitmentNoticeView(RetrieveUpdateAPIView):
    serializer_class = RecruitmentNoticeSerializer
    permission_classes = [CanEditAbout]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_object(self):
        return RecruitmentNotice.objects.get_solo()


class JoinQuestionnaireView(RetrieveUpdateAPIView):
    serializer_class = JoinQuestionnaireSerializer
    permission_classes = [CanEditAbout]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_object(self):
        return Questionnaire.get_join()


class JoinResponseView(ListCreateAPIView):
    serializer_class = JoinResponseSerializer

    def get_queryset(self):
        return Questionnaire.get_join().responses.all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAboutEditor()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        questionnaire = Questionnaire.get_join()
        user = request.user if request.user.is_authenticated else None
        device_id = device_id_from_request(request)
        if user is None:
            if not device_id:
                return Response({"detail": "缺少设备标识"}, status=status.HTTP_400_BAD_REQUEST)
            if questionnaire.responses.filter(user__isnull=True, device_id=device_id).exists():
                return Response({"detail": "你已经提交过了"}, status=status.HTTP_400_BAD_REQUEST)
        elif questionnaire.responses.filter(user=user).exists():
            return Response({"detail": "你已经提交过了"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                instance = serializer.save(
                    questionnaire=questionnaire,
                    user=user,
                    device_id=device_id if user is None else "",
                )
        except IntegrityError:
            return Response({"detail": "你已经提交过了"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"ok": True, "id": instance.pk, "message": "报名已提交，我们会尽快与你联系。"},
            status=status.HTTP_201_CREATED,
        )
