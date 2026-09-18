"""新闻访问控制（遵循 ADR 0005：命名 BasePermission 子类 + has_perm，绝不查组名）。"""
from rest_framework import permissions


class CanManageNews(permissions.BasePermission):
    """新闻写：持 news.manage_news。读匿名开放（视图按 action 分流）。"""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("news.manage_news"))
