from rest_framework import permissions


class CanCreateProposal(permissions.BasePermission):
    """所有登录用户都可以创建申报（反馈）"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanViewProposal(permissions.BasePermission):
    """查看：意见反馈/举报需 proposals.view_feedback 权限（反馈对成员不可见）。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # 反馈可见性：本人或持 view_feedback 权限者（社长）；其余拒绝。
        if obj.creator_id == request.user.pk:
            return True
        return request.user.has_perm("proposals.view_feedback")


class CanModifyProposal(permissions.BasePermission):
    """编辑（仅「已拒绝」可重新提交场景）：创建人，或有 proposals.change_proposal 权限者。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.creator == request.user or request.user.has_perm("proposals.change_proposal")


class CanApproveProposal(permissions.BasePermission):
    """审批（通过/拒绝）：需 proposals.approve_proposal 权限"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("proposals.approve_proposal"))


class CanWithdrawProposal(permissions.BasePermission):
    """撤回：创建人在 待审批 阶段可撤回"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.status != "pending_approval":
            return False
        return obj.creator == request.user
