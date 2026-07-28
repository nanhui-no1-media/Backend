"""统一附件权限：单一抽象规则，父级差异收进 helper（见 ADR 0002）。

> 操作者须为该父级的**创建者**，或该父级的**活跃参与者**，或持有该父级
> **管理权限**者。新增与删除沿用同一套规则。

- 任务：活跃参与者 = 进行中（in_progress）时的负责人 / 协作者；管理权限 = tasks.manage_tasks。
- 申报：活跃参与者 = 空（创建者即唯一参与者）；管理权限 = proposals.change_proposal。

删除时在上述规则之上，额外允许**附件上传者**删除自己上传的附件（用户故事 #12）。
"""
from proposals.models import Proposal
from tasks.lifecycle import is_active_participant
from tasks.models import Task


def is_parent_creator(user, parent):
    """父级创建者（任务/申报的 creator）。"""
    return parent.creator_id is not None and parent.creator_id == user.pk


# 「任务活跃参与者」谓词已收口到 tasks.lifecycle.is_active_participant
# （架构深化 #1），本模块按 (parent, user) 顺序引用之——对外规则不变。


def has_parent_manage_permission(user, parent):
    """父级管理权限：任务 = tasks.manage_tasks；申报 = proposals.change_proposal。"""
    if isinstance(parent, Task):
        return user.has_perm("tasks.manage_tasks")
    if isinstance(parent, Proposal):
        return user.has_perm("proposals.change_proposal")
    return False


def can_manage_parent_attachments(user, parent):
    """单一抽象规则：创建者 / 活跃参与者 / 管理权限。新增与上传均用此函数。"""
    if not user.is_authenticated:
        return False
    if is_parent_creator(user, parent):
        return True
    if isinstance(parent, Task) and is_active_participant(parent, user):
        return True
    if has_parent_manage_permission(user, parent):
        return True
    return False
