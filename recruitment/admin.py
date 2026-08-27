from django.contrib import admin

from .models import RecruitmentNotice


@admin.register(RecruitmentNotice)
class RecruitmentNoticeAdmin(admin.ModelAdmin):
    list_display = ("updated_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
