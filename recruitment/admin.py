from django.contrib import admin

from .models import JoinQuestionnaire, JoinResponse, RecruitmentNotice


@admin.register(RecruitmentNotice)
class RecruitmentNoticeAdmin(admin.ModelAdmin):
    list_display = ("updated_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JoinQuestionnaire)
class JoinQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ("updated_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JoinResponse)
class JoinResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "submitted_at")
    readonly_fields = ("answers", "submitted_at", "user")
