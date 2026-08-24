from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Singleton admin: one row, no add/delete, changelist jumps to the form."""

    fieldsets = (
        ("验证", {"fields": ("verification_enabled",)}),
        (
            "注册与限流",
            {
                "fields": (
                    "registration_enabled",
                    "register_per_ip_per_day",
                    "resend_verification_per_ip_per_hour",
                    "feedback_anon_per_ip_per_day",
                )
            },
        ),
        ("上传", {"fields": ("sync_upload_max_bytes", "tus_media_max_bytes")}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        return HttpResponseRedirect(
            reverse("admin:common_sitesettings_change", args=[obj.pk])
        )
