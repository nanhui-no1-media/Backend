from django.contrib.auth.models import User
from rest_framework import permissions

PRESIDENT_GROUP = "社长"


def is_president(user: User) -> bool:
    """[过渡] 等价 has_perm('tasks.manage_tasks')；Task 9 删除。"""
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
    """任务编辑/删除：仅 pending 状态可改；进入认领/进行后对所有人锁定（含 manage_tasks 权限者）"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if obj.status != "pending":
            return False
        if request.user.has_perm("tasks.manage_tasks"):
            return True
        return obj.creator == request.user


class CanAssignTask(permissions.BasePermission):
    """直接指派：需 tasks.assign_task 权限（社长默认组授予）"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("tasks.assign_task"))


class CanUploadAttachment(permissions.BasePermission):
    """上传附件：manage_tasks 权限者始终可；否则按创建者/负责人/协作者规则。
    delete_attachment 由视图内逻辑进一步限制（上传者/创建者/manage_tasks 可删）。"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.has_perm("tasks.manage_tasks"):
            return True
        if getattr(view, "action", "") == "delete_attachment":
            return True
        if getattr(view, "action", "") == "add_attachment":
            if obj.status == "in_progress":
                if user == obj.creator or user == obj.assignee:
                    return True
                return obj.collaborators.filter(pk=user.pk).exists()
            return user == obj.creator
        return False


class CanManageTag(permissions.BasePermission):
    """标签管理：所有登录用户可读；写需 tasks.manage_tags 权限"""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return user.has_perm("tasks.manage_tags")
