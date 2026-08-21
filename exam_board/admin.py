from django.contrib import admin

from .models import ExamData


@admin.register(ExamData)
class ExamDataAdmin(admin.ModelAdmin):
    list_display = ("exam_date", "exam_title", "exam_list", "updated_at")
    ordering = ("-exam_date", "-id")
