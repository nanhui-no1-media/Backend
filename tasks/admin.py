from django.contrib import admin

from .models import Attachment, Tag, Task, TaskClaimRequest


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ["uploaded_by", "file_type", "file_name", "file_size", "uploaded_at"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "color"]
    search_fields = ["name"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "priority", "creator", "assignee", "due_date", "created_at"]
    list_filter = ["status", "priority"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at", "completed_at"]
    inlines = [AttachmentInline]
    filter_horizontal = ["tags", "collaborators"]


@admin.register(TaskClaimRequest)
class TaskClaimRequestAdmin(admin.ModelAdmin):
    list_display = ["task", "claimant", "status", "reviewed_by", "created_at"]
    list_filter = ["status"]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ["file_name", "task", "uploaded_by", "file_type", "file_size", "uploaded_at"]
    list_filter = ["file_type"]
