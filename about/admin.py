from django.contrib import admin

from .models import AboutPage


@admin.register(AboutPage)
class AboutPageAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at")

    # 单例：禁止新增 / 删除，仅可编辑那一行。
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
