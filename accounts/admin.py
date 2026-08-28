from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery
from django.utils.html import format_html, format_html_join

from common.policy import get_policy

from .identity_review import approve_manual, disable_user, reject_manual
from .models import IdentityProof, Profile, Verification, is_verified


# ---- 审核动作（#31 / ADR-0006）----
# 同时挂在 ProfileAdmin 与 IdentityProofAdmin：queryset 元素都有 .user，按 user 操作其
# manual 验证通道。仅持 accounts.can_review_identity 者可用（get_actions 收口 + 动作内二次校验）。
# 业务路径在 identity_review（与 /auth/identity-reviews/ API 共用）。


def approve_identity(modeladmin, request, queryset):
    """通过身份审核：manual 验证通道置 approved（+ verified_at / verified_by），并发邮件。"""
    if not get_policy().verification_enabled:
        modeladmin.message_user(
            request, "验证通道已关闭，无法通过身份审核。", level=messages.ERROR,
        )
        return
    count = 0
    for obj in queryset.select_related("user"):
        if not request.user.has_perm("accounts.can_review_identity"):
            continue  # 防御：get_actions 已收口，此处双保险
        approve_manual(obj.user, reviewer=request.user)
        count += 1
    modeladmin.message_user(request, f"已通过 {count} 个账号的身份审核。")


approve_identity.short_description = "通过身份审核"


def reject_identity(modeladmin, request, queryset):
    """驳回身份审核：manual 通道置 rejected，并发邮件提示可在面板重交（#38）。"""
    if not get_policy().verification_enabled:
        modeladmin.message_user(
            request, "验证通道已关闭，无法驳回身份审核。", level=messages.ERROR,
        )
        return
    count = 0
    for obj in queryset.select_related("user"):
        if not request.user.has_perm("accounts.can_review_identity"):
            continue
        reject_manual(obj.user, reviewer=request.user)
        count += 1
    modeladmin.message_user(request, f"已驳回 {count} 个账号的身份审核。")


reject_identity.short_description = "驳回身份审核"


def disable_account(modeladmin, request, queryset):
    """停用账号：置 is_active=False，并发邮件通知当事人联系信息组。"""
    count = 0
    for obj in queryset.select_related("user"):
        if not request.user.has_perm("accounts.can_review_identity"):
            continue
        disable_user(obj.user)
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


class ManualChannelStatusFilter(admin.SimpleListFilter):
    """按该用户人工通道 Verification 状态过滤身份证明行。"""

    title = "人工通道状态"
    parameter_name = "manual_status"

    def lookups(self, request, model_admin):
        return Verification.STATUSES

    def queryset(self, request, qs):
        value = self.value()
        if not value:
            return qs
        return qs.filter(
            user_id__in=Verification.objects.filter(
                channel=Verification.CHANNEL_MANUAL, status=value,
            ).values("user_id")
        )


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

    list_display = ("id", "user", "uploaded_at", "manual_channel_status", "proof_thumb")
    readonly_fields = ("user", "uploaded_at", "proof_image")
    search_fields = ("user__username", "user__email")
    list_filter = (ManualChannelStatusFilter, "uploaded_at")
    actions = list(_IDENTITY_ACTIONS)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        manual = Verification.objects.filter(
            user_id=OuterRef("user_id"),
            channel=Verification.CHANNEL_MANUAL,
        )
        return qs.annotate(manual_status=Subquery(manual.values("status")[:1]))

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

    @admin.display(description="人工通道状态", ordering="manual_status")
    def manual_channel_status(self, obj):
        status = getattr(obj, "manual_status", None)
        if not status:
            return "—"
        return dict(Verification.STATUSES).get(status, status)

    @admin.display(description="缩略图")
    def proof_thumb(self, obj):
        if not obj.pk:
            return "-"
        url = f"/auth/identity-proof/{obj.pk}/"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" style="max-height:240px;border-radius:4px" />'
            "</a>",
            url,
            url,
        )

    @admin.display(description="证明材料")
    def proof_image(self, obj):
        if not obj.pk:
            return "-"
        proofs = IdentityProof.objects.filter(user_id=obj.user_id).order_by("-uploaded_at")
        return format_html_join(
            "",
            '<img src="/auth/identity-proof/{}/" alt="身份证明" '
            'style="max-width:100%;max-height:72vh;display:block;'
            'margin:0 auto 16px;border-radius:6px" />',
            ((p.pk,) for p in proofs),
        )


class ProfileInline(admin.StackedInline):
    model = Profile
    fk_name = "user"  # Profile 仅 user 一个 FK→User；显式绑定，防后续新增 FK 时歧义


class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    inlines = [ProfileInline]
    actions = ["ban_users", "mute_users"]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm("messaging.mute_user"):
            actions.pop("mute_users", None)
        return actions

    @admin.action(description="封禁")
    def ban_users(self, request, queryset):
        """批量封禁：停用账号、吊销会话、发邮件。不可封禁自己或超级管理员。"""
        ok = skip = 0
        for user in queryset:
            if user.pk == request.user.pk or user.is_superuser or not user.is_active:
                skip += 1
                continue
            disable_user(user)
            ok += 1
        self.message_user(request, f"已封禁 {ok} 个账号。跳过 {skip} 个。")

    @admin.action(description="全站禁言")
    def mute_users(self, request, queryset):
        """批量全站禁言（永久）。需 messaging.mute_user；已禁言 / 自己跳过。"""
        from messaging.services import MessagingError, mute_user

        if not request.user.has_perm("messaging.mute_user"):
            self.message_user(request, "没有全站禁言权限。", level=messages.ERROR)
            return
        ok = skip = 0
        for user in queryset:
            try:
                mute_user(request.user, user, reason="后台批量禁言")
                ok += 1
            except MessagingError:
                skip += 1
        self.message_user(request, f"已禁言 {ok} 个账号。跳过 {skip} 个。")


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(IdentityProof, IdentityProofAdmin)
