from django.contrib import admin

from .models import Tag, Task, TaskClaimRequest


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "color"]
    search_fields = ["name"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "priority", "creator", "assignee", "created_at"]
    list_filter = ["status", "priority"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at", "completed_at"]
    filter_horizontal = ["tags", "collaborators"]


@admin.register(TaskClaimRequest)
class TaskClaimRequestAdmin(admin.ModelAdmin):
    list_display = ["task", "claimant", "status", "reviewed_by", "created_at"]
    list_filter = ["status"]
