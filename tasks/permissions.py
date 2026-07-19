from django.contrib.auth.models import User
from rest_framework import permissions

PRESIDENT_GROUP = "社长"


def is_president(user: User) -> bool:
    # 角色→权限：社长默认组被授予 tasks.manage_tasks；直接授予该权限亦生效。
    return bool(user and user.is_authenticated and user.has_perm("tasks.manage_tasks"))


class CanCreateTask(permissions.BasePermission):
    """所有登录用户都可以创建任务"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class CanViewTask(permissions.BasePermission):
    """所有登录用户都能查看所有任务"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return True


class CanModifyTask(permissions.BasePermission):
    """任务编辑/删除：仅 pending 状态可改；进入认领/进行后对所有人锁定（含社长）"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if obj.status != "pending":
            return False
        if is_president(request.user):
            return True
        return obj.creator == request.user


class CanAssignTask(permissions.BasePermission):
    """直接指派：仅社长"""

    def has_permission(self, request, view):
        user = request.user
        return user and user.is_authenticated and is_president(user)


class CanUploadAttachment(permissions.BasePermission):
    """上传附件权限：
    - 初始阶段（非 in_progress）：仅任务创建者可上传
    - 任务进入 in_progress（认领已批准并指派负责人）后：创建者、负责人和协作者可上传
    - 社长始终有权限
    - delete_attachment 操作由视图内的逻辑进一步限制（上传者或创建者或社长可删除）
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # 社长始终有权限
        if is_president(user):
            return True
        # 删除接口由视图内部做更细粒度控制，允许继续执行以便视图检查上传者
        if getattr(view, "action", "") == "delete_attachment":
            return True
        # 添加附件的权限规则
        if getattr(view, "action", "") == "add_attachment":
            # 如果任务已进入进行中，则创建者/负责人/协作者可上传
            if obj.status == "in_progress":
                if user == obj.creator or user == obj.assignee:
                    return True
                return obj.collaborators.filter(pk=user.pk).exists()
            # 否则仅创建者可上传
            return user == obj.creator
        # 其它操作默认拒绝
        return False


class CanManageTag(permissions.BasePermission):
    """标签管理：社长可写；所有登录用户可读"""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_president(user)
