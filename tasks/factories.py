"""测试共享夹具：供 tasks 的各测试模块（HTTP 冒烟、生命周期接口等）复用。

抽出此处以免 ``make_president`` 之类的助手在多个测试文件里各自复制、渐行渐远。
"""

from django.contrib.auth.models import Group


def make_president(user):
    """把用户加入「社长」组（默认组已由迁移授予 manage_tasks / assign_task 等权限）。"""
    group, _ = Group.objects.get_or_create(name="社长")
    user.groups.add(group)
    return user
