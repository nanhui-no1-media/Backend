from django.contrib import admin

from .models import Tutorial, TutorialTag


@admin.register(TutorialTag)
class TutorialTagAdmin(admin.ModelAdmin):
    list_display = ("kind", "order", "name")
    list_filter = ("kind",)
    ordering = ("kind", "order")


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ("title", "file_type", "uploader", "views", "created_at")
    list_filter = ("file_type",)
    search_fields = ("title", "file_name")
    autocomplete_fields = ("uploader",)
    filter_horizontal = ("tags",)
