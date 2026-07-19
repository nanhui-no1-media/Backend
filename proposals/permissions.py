from rest_framework import permissions


class CanCreateProposal(permissions.BasePermission):
    """所有登录用户都可以创建申报"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanViewProposal(permissions.BasePermission):
    """查看：活动申报所有登录用户可见；意见反馈/举报需 proposals.view_feedback 权限"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.proposal_type == "activity":
            return True
        return request.user.has_perm("proposals.view_feedback")


class CanModifyProposal(permissions.BasePermission):
    """编辑（仅「已打回」）：创建人，或有 proposals.change_proposal 权限者。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.status != "returned":
            return False
        return obj.creator == request.user or request.user.has_perm("proposals.change_proposal")


class CanVoteProposal(permissions.BasePermission):
    """投票：全体成员对「投票中」活动申报可投，每人一次（视图内去重）"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.proposal_type == "activity" and obj.status == "voting"


class CanApproveProposal(permissions.BasePermission):
    """审批（通过/打回/拒绝）：需 proposals.approve_proposal 权限"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("proposals.approve_proposal"))


class CanWithdrawProposal(permissions.BasePermission):
    """撤回：创建人在 投票中/待审批 阶段可撤回"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.status not in ("voting", "pending_approval"):
            return False
        return obj.creator == request.user


class CanManageProposalAttachment(permissions.BasePermission):
    """附件：有 change_proposal 权限者，或申报创建人（已打回可改/补材料）"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.has_perm("proposals.change_proposal"):
            return True
        if getattr(view, "action", "") == "delete_attachment":
            return True
        return obj.creator == request.user
