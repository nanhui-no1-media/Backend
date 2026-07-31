from rest_framework.permissions import BasePermission, SAFE_METHODS


class AboutPagePermission(BasePermission):
    """关于页权限：所有人（含匿名）可读；写需 about.change_aboutpage。"""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.has_perm("about.change_aboutpage")
        )
