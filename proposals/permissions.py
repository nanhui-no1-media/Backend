from rest_framework import permissions

from tasks.permissions import is_president  # 复用社长判定


class CanCreateProposal(permissions.BasePermission):
    """所有登录用户都可以创建申报"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanViewProposal(permissions.BasePermission):
    """查看权限：
    - 活动申报：所有登录用户可见
    - 意见反馈/举报：仅社长可见（公开匿名提交，保密）
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.proposal_type == "activity":
            return True
        # 反馈/举报：仅社长
        return is_president(request.user)


class CanModifyProposal(permissions.BasePermission):
    """编辑：仅「已打回」状态。创建人可改自己的（活动申报）；
    社长也可改（反馈/举报无创建人，打回后由社长修订）。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.status != "returned":
            return False
        return obj.creator == request.user or is_president(request.user)


class CanVoteProposal(permissions.BasePermission):
    """投票：全体成员对「投票中」的活动申报可投，每人一次（视图内做去重）"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.proposal_type == "activity" and obj.status == "voting"


class CanApproveProposal(permissions.BasePermission):
    """审批（通过/打回/拒绝）：仅社长"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and is_president(user))


class CanWithdrawProposal(permissions.BasePermission):
    """撤回：创建人在 投票中/待审批 阶段可撤回"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.status not in ("voting", "pending_approval"):
            return False
        return obj.creator == request.user


class CanManageProposalAttachment(permissions.BasePermission):
    """附件：社长，或申报创建人（已打回可改、其它阶段可补充材料）"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_president(user):
            return True
        # 删除接口由视图内部做更细粒度控制（上传者或创建人或社长）
        if getattr(view, "action", "") == "delete_attachment":
            return True
        return obj.creator == user
