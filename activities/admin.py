from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from common.surveyjs_admin import SurveyJSAdminMixin

from .lifecycle import can_edit_schema
from .models import (
    Activity, Ballot, BallotSelection, Submission, SurveyResponse, VoteOption,
)


@admin.register(Activity)
class ActivityAdmin(SurveyJSAdminMixin, admin.ModelAdmin):
    list_display = ["title", "type", "status", "audience", "creator", "end_at", "created_at"]
    list_filter = ["type", "status", "audience"]
    search_fields = ["title", "body"]
    date_hierarchy = "created_at"

    def survey_is_applicable(self, obj):
        return obj.type == "survey"

    def survey_can_save_schema(self, obj):
        return can_edit_schema(obj)

    def survey_locked_message(self, obj):
        return "已有作答或已截止，问卷 Schema 已锁定。"

    def iter_survey_responses(self, obj):
        for row in obj.survey_responses.select_related("user").all():
            yield {
                "answers": row.answers or {},
                "user_label": row.user.username if row.user_id else "访客",
                "submitted_at": row.submitted_at,
                "admin_url": reverse("admin:activities_surveyresponse_change", args=[row.pk]),
            }


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ["activity", "user", "submitted_at", "dashboard_link"]
    list_filter = ["activity"]
    search_fields = ["activity__title", "user__username"]
    autocomplete_fields = ["activity", "user"]
    readonly_fields = ["answers", "submitted_at"]
    date_hierarchy = "submitted_at"
    change_form_template = "admin/surveyjs/change_form.html"

    def _results_url(self, obj):
        if not obj or not obj.activity_id:
            return None
        return reverse("admin:activities_activity_survey_results", args=[obj.activity_id])

    @admin.display(description="统计")
    def dashboard_link(self, obj):
        url = self._results_url(obj)
        if not url:
            return "—"
        return format_html('<a href="{}">统计</a>', url)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        url = self._results_url(obj)
        if url:
            extra_context["survey_results_url"] = url
        return super().change_view(request, object_id, form_url, extra_context=extra_context)


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
