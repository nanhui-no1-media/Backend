from django.contrib import admin
from django.utils.html import format_html

from .models import Feedback, ReportCase, Review

_TARGET_HASH = (
    ("news_id", "/news/{}"),
    ("activity_id", "/activity/{}"),
    ("tutorial_id", "/tutorials/{}"),
)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "news", "activity", "tutorial", "reviewer", "reviewed_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["comment", "news__title", "activity__title", "tutorial__title"]
    readonly_fields = [
        "news", "activity", "tutorial", "reviewer",
        "reviewed_at", "created_at", "updated_at", "target_preview",
    ]
    fieldsets = (
        (None, {"fields": ("status", "comment", "reviewer", "reviewed_at")}),
        ("对象", {"fields": ("news", "activity", "tutorial")}),
        ("预览", {"fields": ("target_preview",)}),
    )

    class Media:
        css = {"all": ["reviews/admin_preview.css"]}

    @admin.display(description="对象界面")
    def target_preview(self, obj):
        if not obj or not obj.pk:
            return "—"
        path = None
        for attr, tmpl in _TARGET_HASH:
            pk = getattr(obj, attr, None)
            if pk:
                path = tmpl.format(pk)
                break
        if not path:
            return "—"
        src = f"/#{path}?embed=1"
        return format_html(
            '<p style="margin:0 0 8px">'
            '<a href="{}" target="_blank" rel="noopener">新标签打开</a></p>'
            '<iframe src="{}" title="对象界面" '
            'style="width:100%;height:80vh;border:1px solid #d0d5dd;'
            'border-radius:8px;background:#fff"></iframe>',
            src,
            src,
        )


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "category", "status", "creator", "closed_by", "created_at"]
    list_filter = ["status", "category"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at", "closed_at"]


@admin.register(ReportCase)
class ReportCaseAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "news", "activity", "tutorial", "comment", "reported_user", "resolved_by", "created_at"]
    list_filter = ["status"]
    search_fields = ["resolution_comment"]
    readonly_fields = ["created_at", "updated_at", "resolved_at"]
