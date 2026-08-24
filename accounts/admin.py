from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import format_html

from common.policy import get_policy

from .models import IdentityProof, Profile, UserSession, Verification, is_verified


def _revoke_user_sessions(user):
    """立即吊销用户既有会话：删 Django Session 行（强制登出）+ 清 UserSession.is_current。

    is_active=False 只挡新登录；不吊销既有会话的话，被停用账号仍可用当前会话直到过期。
    """
    from django.contrib.sessions.models import Session

    keys = list(UserSession.objects.filter(user=user).values_list("session_key", flat=True))
    UserSession.objects.filter(user=user).update(is_current=False)
    if keys:
        Session.objects.filter(session_key__in=keys).delete()


# ---- 审核动作（#31 / ADR-0006）----
# 同时挂在 ProfileAdmin 与 IdentityProofAdmin：queryset 元素都有 .user，按 user 操作其
# manual 验证通道。仅持 accounts.can_review_identity 者可用（get_actions 收口 + 动作内二次校验）。


def approve_identity(modeladmin, request, queryset):
    """通过身份审核：manual 验证通道置 approved（+ verified_at / verified_by），并发邮件。

    验证态单一事实源是 Verification 行（ADR-0006），不再写 Profile 布尔。任一通道 approved
    ⇒ 账号已验证（写门禁 / 徽章 / 面板随之放行）。
    """
    if not get_policy().verification_enabled:
        modeladmin.message_user(
            request, "验证通道已关闭，无法通过身份审核。", level=messages.ERROR,
        )
        return
    now = timezone.now()
    count = 0
    for obj in queryset.select_related("user"):
        user = obj.user
        if not request.user.has_perm("accounts.can_review_identity"):
            continue  # 防御：get_actions 已收口，此处双保险
        verification, _ = Verification.objects.get_or_create(
            user=user, channel=Verification.CHANNEL_MANUAL,
            defaults={"status": Verification.STATUS_APPROVED, "verified_at": now,
                      "verified_by": request.user},
        )
        if verification.status != Verification.STATUS_APPROVED:
            verification.status = Verification.STATUS_APPROVED
            verification.verified_at = now
            verification.verified_by = request.user
            verification.save(update_fields=["status", "verified_at", "verified_by"])
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


def reject_identity(modeladmin, request, queryset):
    """驳回身份审核：manual 通道置 rejected，并发邮件提示可在面板重交（#38）。

    驳回 ≠ 停用账号：账号仍可登录（访客）、可重交证明；仅 manual 通道记驳回态。
    """
    if not get_policy().verification_enabled:
        modeladmin.message_user(
            request, "验证通道已关闭，无法驳回身份审核。", level=messages.ERROR,
        )
        return
    count = 0
    for obj in queryset.select_related("user"):
        user = obj.user
        if not request.user.has_perm("accounts.can_review_identity"):
            continue
        verification, _ = Verification.objects.get_or_create(
            user=user, channel=Verification.CHANNEL_MANUAL,
            defaults={"status": Verification.STATUS_REJECTED},
        )
        if verification.status != Verification.STATUS_REJECTED:
            verification.status = Verification.STATUS_REJECTED
            verification.verified_at = None
            verification.verified_by = None
            verification.save(update_fields=["status", "verified_at", "verified_by"])
        send_mail(
            subject="身份审核已驳回 - 南汇一中传媒社",
            message="你的身份证明未通过审核。请在「账号验证」面板重新提交更清晰的证明材料。",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=True,
        )
        count += 1
    modeladmin.message_user(request, f"已驳回 {count} 个账号的身份审核。")


reject_identity.short_description = "驳回身份审核"


def disable_account(modeladmin, request, queryset):
    """停用账号：置 is_active=False，并发邮件通知当事人联系信息组。

    账号级动作，与验证通道无关——被停用账号既不能登录、既有会话也被立即吊销。
    """
    count = 0
    for obj in queryset.select_related("user"):
        user = obj.user
        if not request.user.has_perm("accounts.can_review_identity"):
            continue
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
            _revoke_user_sessions(user)  # 立即吊销既有会话，防被停用账号继续访问
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


_IDENTITY_ACTIONS = (approve_identity, reject_identity, disable_account)


class _IdentityReviewActionsMixin:
    """只把审核动作暴露给持 can_review_identity 者。"""

    def get_actions(self, request):
        actions = super().get_actions(request)  # type: ignore[misc]
        if not request.user.has_perm("accounts.can_review_identity"):
            for fn in _IDENTITY_ACTIONS:
                actions.pop(fn.__name__, None)
        return actions


class VerifiedFilter(admin.SimpleListFilter):
    """按账号「已验证」过滤（任一 Verification 通道 approved 即已验证）。"""

    title = "验证状态"
    parameter_name = "verified"

    def lookups(self, request, model_admin):
        return [("yes", "已验证"), ("no", "未验证")]

    def queryset(self, request, qs):
        approved = Profile.objects.filter(
            user__pk__in=Verification.objects.filter(
                status=Verification.STATUS_APPROVED
            ).values_list("user_id", flat=True)
        )
        if self.value() == "yes":
            return qs.filter(pk__in=approved)
        if self.value() == "no":
            return qs.exclude(pk__in=approved)
        return qs


class ProfileAdmin(_IdentityReviewActionsMixin, admin.ModelAdmin):
    list_display = ("user", "real_name", "identity", "verified")
    list_filter = (VerifiedFilter, "identity")
    search_fields = ("user__username", "user__email", "real_name")
    actions = list(_IDENTITY_ACTIONS)

    @admin.display(boolean=True, description="已验证")
    def verified(self, obj):
        return is_verified(obj.user)


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
    fk_name = "user"  # Profile 仅 user 一个 FK→User；显式绑定，防后续新增 FK 时歧义


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
