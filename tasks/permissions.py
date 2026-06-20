from django.contrib.auth.models import User
from rest_framework import permissions

PRESIDENT_GROUP = "社长"


def is_president(user: User) -> bool:
    return user.groups.filter(name=PRESIDENT_GROUP).exists()


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
    """所有登录用户都能上传附件"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return True


class CanManageTag(permissions.BasePermission):
    """标签管理：社长可写；所有登录用户可读"""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_president(user)
