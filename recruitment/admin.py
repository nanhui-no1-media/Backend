from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from common.surveyjs_admin import SurveyJSAdminMixin

from .models import JoinQuestionnaire, JoinResponse, RecruitmentNotice


@admin.register(RecruitmentNotice)
class RecruitmentNoticeAdmin(admin.ModelAdmin):
    list_display = ("updated_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JoinQuestionnaire)
class JoinQuestionnaireAdmin(SurveyJSAdminMixin, admin.ModelAdmin):
    list_display = ("updated_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def iter_survey_responses(self, obj):
        for row in JoinResponse.objects.select_related("user").all():
            yield {
                "answers": row.answers or {},
                "user_label": row.user.username if row.user_id else "访客",
                "submitted_at": row.submitted_at,
                "admin_url": reverse("admin:recruitment_joinresponse_change", args=[row.pk]),
            }


@admin.register(JoinResponse)
class JoinResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "submitted_at", "dashboard_link")
    readonly_fields = ("answers", "submitted_at", "user")
    change_form_template = "admin/surveyjs/change_form.html"

    @admin.display(description="统计")
    def dashboard_link(self, obj):
        url = reverse(
            "admin:recruitment_joinquestionnaire_survey_results",
            args=[JoinQuestionnaire.objects.get_solo().pk],
        )
        return format_html('<a href="{}">统计</a>', url)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["survey_results_url"] = reverse(
            "admin:recruitment_joinquestionnaire_survey_results",
            args=[JoinQuestionnaire.objects.get_solo().pk],
        )
        return super().change_view(request, object_id, form_url, extra_context=extra_context)
