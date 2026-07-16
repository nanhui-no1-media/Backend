from rest_framework import permissions

INFO_GROUP = "信息组"


def is_info_group(user) -> bool:
    """是否属于「信息组」（负责新闻发布与账户分发）。"""
    return bool(
        user
        and user.is_authenticated
        and user.groups.filter(name=INFO_GROUP).exists()
    )


class CanManageNews(permissions.BasePermission):
    """新闻发布 / 编辑 / 删除：仅「信息组」成员或超级用户。

    读（list/retrieve）由视图层 AllowAny 放行，不走此权限。
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (is_info_group(user) or user.is_superuser))
