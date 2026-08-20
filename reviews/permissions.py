from rest_framework import permissions


class CanModerateReview(permissions.BasePermission):
    """审核队列读写：持 reviews.moderate。"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("reviews.moderate"))
