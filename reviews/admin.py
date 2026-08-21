from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "news", "activity", "tutorial", "reviewer", "reviewed_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["comment", "news__title", "activity__title", "tutorial__title"]
    readonly_fields = ["created_at", "updated_at", "reviewed_at"]
