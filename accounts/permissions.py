from rest_framework import permissions

from .models import is_verified


class IsVerified(permissions.BasePermission):
    """写操作门槛（ADR-0006）：已登录且账号已验证（任一验证通道 approved）才放行。

    取代旧的 ``IsIdentityVerified``（读 profile.identity_verified）——验证态单一事实源是
    ``is_verified``（任一通道 approved）。作用域不变：只挂到对外可见的**写**动作（建任务 /
    发消息 / 建申报 / 投票 等）的 permission_classes，不挂读动作——故此处不做 SAFE_METHODS
    旁路（粒度由各 ViewSet 的 get_permissions 控制）。

    超级用户是唯一应用访问逃生舱（ADR-0005 决策 9）：``is_verified`` 纯计算不含它，门禁在此放行。
    """

    message = "请先完成账号验证后再使用此功能（发帖 / 发消息 / 建申报等）。"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or is_verified(user)


class CanReviewIdentity(permissions.BasePermission):
    """身份审核队列读写：持 accounts.can_review_identity。"""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.has_perm("accounts.can_review_identity")
        )
