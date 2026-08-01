from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import format_html

from .models import IdentityProof, Profile


# ---- 审核动作（#31）----
# 同时挂在 ProfileAdmin 与 IdentityProofAdmin：queryset 元素都有 .user，按 user 审批 / 停用。
# 仅持 accounts.can_review_identity 者可用（get_actions 收口 + 动作内二次校验）。


def approve_identity(modeladmin, request, queryset):
    """通过身份审核：置 identity_verified=True + verified_at / verified_by，并发邮件通知。"""
    now = timezone.now()
    count = 0
    for obj in queryset.select_related("user", "user__profile"):
        user = obj.user
        if not request.user.has_perm("accounts.can_review_identity"):
            continue  # 防御：get_actions 已收口，此处双保险
        profile = getattr(user, "profile", None)
        if profile is None:
            profile = Profile.objects.create(user=user)
        if not profile.identity_verified:
            profile.identity_verified = True
            profile.verified_at = now
            profile.verified_by = request.user
            profile.save(update_fields=["identity_verified", "verified_at", "verified_by"])
        send_mail(
            subject="身份审核已通过 - 南汇一中传媒社",
            message="你的身份证明已通过审核，现在可以使用全部功能（发帖 / 发消息 / 建申报等）。",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=True,
        )
        count += 1
    modeladmin.message_user(request, f"已通过 {count} 个账号的身份审核。")


approve_identity.short_description = "通过身份审核"


def disable_account(modeladmin, request, queryset):
    """停用账号：置 is_active=False，并发邮件通知当事人联系信息组。"""
    count = 0
    for obj in queryset.select_related("user"):
        user = obj.user
        if not request.user.has_perm("accounts.can_review_identity"):
            continue
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        send_mail(
            subject="账号已被停用 - 南汇一中传媒社",
            message="你的账号已被停用。如有疑问，请联系信息组。",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=True,
        )
        count += 1
    modeladmin.message_user(request, f"已停用 {count} 个账号。")


disable_account.short_description = "停用账号"


_IDENTITY_ACTIONS = (approve_identity, disable_account)


class _IdentityReviewActionsMixin:
    """只把审核动作暴露给持 can_review_identity 者。"""

    def get_actions(self, request):
        actions = super().get_actions(request)  # type: ignore[misc]
        if not request.user.has_perm("accounts.can_review_identity"):
            for fn in _IDENTITY_ACTIONS:
                actions.pop(fn.__name__, None)
        return actions


class ProfileAdmin(_IdentityReviewActionsMixin, admin.ModelAdmin):
    list_display = (
        "user", "real_name", "identity",
        "email_verified", "identity_verified", "verified_at", "verified_by",
    )
    list_filter = ("identity_verified", "email_verified", "identity")
    search_fields = ("user__username", "user__email", "real_name")
    actions = list(_IDENTITY_ACTIONS)


class IdentityProofAdmin(_IdentityReviewActionsMixin, admin.ModelAdmin):
    """身份证明材料（审计留底）：只读浏览 + 审核动作；图经鉴权下载视图服务（不经公开 MEDIA_URL）。"""

    list_display = ("id", "user", "uploaded_at", "proof_thumb")
    readonly_fields = ("user", "uploaded_at", "proof_image")
    search_fields = ("user__username", "user__email")
    list_filter = ("uploaded_at",)
    actions = list(_IDENTITY_ACTIONS)
    # 永久留底：不允许增 / 改 / 删
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # 仅持 can_review_identity 者可见此审核台（含证明图）
    def has_module_permission(self, request):
        return request.user.has_perm("accounts.can_review_identity")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("accounts.can_review_identity")

    @admin.display(description="缩略图")
    def proof_thumb(self, obj):
        if not obj.pk:
            return "-"
        return format_html('<img src="/auth/identity-proof/{}/" style="max-height:72px;border-radius:4px" />', obj.pk)

    @admin.display(description="证明材料")
    def proof_image(self, obj):
        if not obj.pk:
            return "-"
        return format_html('<img src="/auth/identity-proof/{}/" style="max-width:600px;border-radius:6px" />', obj.pk)


class ProfileInline(admin.StackedInline):
    model = Profile
    fk_name = "user"  # Profile 有 user + verified_by 两个 FK→User，须指明内联绑哪个
    can_delete = False


class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    inlines = [ProfileInline]


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(IdentityProof, IdentityProofAdmin)
