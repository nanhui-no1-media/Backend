from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from about.permissions import CanEditAbout

from .models import JoinQuestionnaire, JoinResponse, RecruitmentNotice
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


class RecruitmentLandingView(APIView):
    """GET /recruitment/：公告 + 问卷 Schema，公开可读。"""

    permission_classes = [AllowAny]

    def get(self, request):
        notice = RecruitmentNotice.objects.get_solo()
        questionnaire = JoinQuestionnaire.objects.get_solo()
        return Response({
            "notice": RecruitmentNoticeSerializer(notice).data,
            "schema": questionnaire.schema,
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
        return JoinQuestionnaire.objects.get_solo()


class JoinResponseView(ListCreateAPIView):
    serializer_class = JoinResponseSerializer
    queryset = JoinResponse.objects.all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAboutEditor()]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {"ok": True, "id": serializer.instance.pk, "message": "报名已提交，我们会尽快与你联系。"},
            status=status.HTTP_201_CREATED,
        )
