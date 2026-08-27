from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from common.surveyjs_admin import SurveyJSAdminMixin, SurveyJSResponseViewMixin

from .lifecycle import can_edit_schema
from .models import (
    Activity, Ballot, BallotSelection, Questionnaire, QuestionnaireResponse,
    Submission, VoteOption,
)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = [
        "title", "type", "status", "audience", "questionnaire_link",
        "creator", "end_at", "created_at",
    ]
    list_filter = ["type", "status", "audience"]
    search_fields = ["title", "body"]
    autocomplete_fields = ["questionnaire", "creator"]
    date_hierarchy = "created_at"

    @admin.display(description="问卷")
    def questionnaire_link(self, obj):
        if not obj.questionnaire_id:
            return "—"
        url = reverse("admin:activities_questionnaire_change", args=[obj.questionnaire_id])
        return format_html('<a href="{}">{}</a>', url, obj.questionnaire)


@admin.register(Questionnaire)
class QuestionnaireAdmin(SurveyJSAdminMixin, admin.ModelAdmin):
    list_display = ["id", "kind", "schema_title", "activity_link", "updated_at"]
    list_filter = ["kind"]
    search_fields = ["id", "kind"]
    date_hierarchy = "updated_at"

    def schema_title(self, obj):
        return (obj.schema or {}).get("title") or "—"
    schema_title.short_description = "标题"

    @admin.display(description="调研活动")
    def activity_link(self, obj):
        activity = getattr(obj, "survey_activity", None)
        if activity is None:
            return "—"
        url = reverse("admin:activities_activity_change", args=[activity.pk])
        return format_html('<a href="{}">{}</a>', url, activity.title)

    def survey_can_save_schema(self, obj):
        if obj.kind == Questionnaire.KIND_JOIN:
            return True
        activity = getattr(obj, "survey_activity", None)
        if activity is None:
            return not obj.responses.exists()
        return can_edit_schema(activity)

    def survey_locked_message(self, obj):
        return "已有作答或已截止，问卷 Schema 已锁定。"

    def iter_survey_responses(self, obj):
        for row in obj.responses.select_related("user").all():
            yield {
                "answers": row.answers or {},
                "user_label": (
                    row.user.username if row.user_id
                    else (f"访客 · {row.device_id[:8]}" if row.device_id else "访客")
                ),
                "submitted_at": row.submitted_at,
                "admin_url": reverse(
                    "admin:activities_questionnaireresponse_survey_view", args=[row.pk],
                ),
            }

    def has_add_permission(self, request):
        # 调研问卷随活动创建；加入问卷为单例。后台不直接新建。
        return False

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.kind == Questionnaire.KIND_JOIN:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(SurveyJSResponseViewMixin, admin.ModelAdmin):
    list_display = [
        "questionnaire", "user", "device_id", "submitted_at",
        "response_link", "dashboard_link",
    ]
    list_filter = ["questionnaire__kind"]
    search_fields = ["questionnaire__schema", "user__username", "device_id"]
    autocomplete_fields = ["questionnaire", "user"]
    readonly_fields = ["answers", "submitted_at", "device_id"]
    date_hierarchy = "submitted_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("questionnaire", "user")

    def _results_url(self, obj):
        if not obj or not obj.questionnaire_id:
            return None
        return reverse(
            "admin:activities_questionnaire_survey_results", args=[obj.questionnaire_id],
        )

    def get_response_stats_url(self, obj):
        return self._results_url(obj)

    @admin.display(description="查看作答")
    def response_link(self, obj):
        url = reverse("admin:activities_questionnaireresponse_survey_view", args=[obj.pk])
        return format_html('<a href="{}">查看作答</a>', url)

    @admin.display(description="统计")
    def dashboard_link(self, obj):
        url = self._results_url(obj)
        if not url:
            return "—"
        return format_html('<a href="{}">统计</a>', url)


@admin.register(VoteOption)
class VoteOptionAdmin(admin.ModelAdmin):
    list_display = ["text", "activity", "order", "created_at"]
    list_filter = ["activity__type"]
    search_fields = ["text"]
    autocomplete_fields = ["activity"]


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    list_display = ["activity", "voter", "created_at"]
    list_filter = ["activity__type"]
    search_fields = ["activity__title", "voter__username"]
    autocomplete_fields = ["activity", "voter"]


@admin.register(BallotSelection)
class BallotSelectionAdmin(admin.ModelAdmin):
    list_display = ["ballot", "option", "created_at"]
    search_fields = ["option__text"]
    autocomplete_fields = ["ballot", "option"]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["activity", "submitter", "review_status", "reviewed_at", "created_at"]
    list_filter = ["review_status", "activity__type"]
    search_fields = ["activity__title", "submitter__username", "review_comment"]
    autocomplete_fields = ["activity", "submitter", "reviewed_by"]
