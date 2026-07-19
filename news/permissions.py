from rest_framework import permissions

INFO_GROUP = "信息组"


def is_info_group(user) -> bool:
    """是否属于「信息组」（负责新闻发布与账户分发）。"""
    # 角色→权限：信息组默认组被授予 news.add_news（及 change/delete）。
    return bool(user and user.is_authenticated and user.has_perm("news.add_news"))
