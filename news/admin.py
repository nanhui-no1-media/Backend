from django.contrib import admin

from .models import News


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "author", "featured", "is_published", "views", "published_at"]
    list_filter = ["category", "featured", "is_published"]
    search_fields = ["title", "summary", "content"]
    readonly_fields = ["views", "published_at", "created_at", "updated_at"]
    filter_horizontal = ["tags"]
    date_hierarchy = "published_at"
