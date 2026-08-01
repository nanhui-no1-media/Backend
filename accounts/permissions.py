from rest_framework import permissions


class IsIdentityVerified(permissions.BasePermission):
    """桶2 写权限门槛（#30）：已登录且身份已审核（profile.identity_verified）才放行。

    无 profile 的存量 / admin / 测试用户视为已审核（保持既有行为）——自助注册是唯一
    创建「未审核」profile 的路径（register 视图显式置 identity_verified=False，由 #28 测试钉死）。

    设计：只挂到对外可见的**写**动作（建任务 / 发消息 / 建申报 / 投票 等）的 permission_classes，
    不挂读动作——故此处不做 SAFE_METHODS 旁路（粒度由各 ViewSet 的 get_permissions 控制）。
    """

    message = "你的身份证明待审核，发帖 / 发消息 / 建申报暂不可用。"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, "profile", None)
        return profile is None or profile.identity_verified
