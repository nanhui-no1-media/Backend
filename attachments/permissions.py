"""统一附件权限：单一抽象规则，父级差异收进 helper（见 ADR 0002）。

> 操作者须为该父级的**创建者**，或该父级的**活跃参与者**，或持有该父级
> **管理权限**者。

- 任务：活跃参与者 = 进行中（in_progress）时的负责人 / 协作者；管理权限 = tasks.manage_tasks。
- 申报：活跃参与者 = 空（创建者即唯一参与者）；管理权限 = proposals.change_proposal。

**上传**走 ``can_upload_to_parent``：反馈父级在此之上做 carve-out——仅署名创建者 + 审结前，
社长被排除（不上传证据到别人反馈）。**删除**走 ``can_manage_parent_attachments``（通用规则），
并额外允许附件上传者删除自己上传的（用户故事 #12）。故社长对反馈「能删不能传」。
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
    """通用管理规则：创建者 / 活跃参与者 / 管理权限。**删除**附件沿用本函数。

    **上传**走 ``can_upload_to_parent``——反馈父级在此之上做了 carve-out（仅署名创建者
    + 审结前，排除社长）；其余父级上传与删除规则一致。故社长对反馈「能删不能传」。
    """
    if not user.is_authenticated:
        return False
    if is_parent_creator(user, parent):
        return True
    if isinstance(parent, Task) and is_active_participant(parent, user):
        return True
    if has_parent_manage_permission(user, parent):
        return True
    return False


def can_upload_to_parent(user, parent):
    """上传附件到父级的权限（ADR 0002 单一规则的反馈 carve-out）。

    反馈特例：仅**署名创建者**、且仅 ``pending_approval`` 期间可上传——社长被排除
    （不上传证据到别人反馈），审结（通过/拒绝）即锁死。其余父级沿用通用规则。
    """
    if not user.is_authenticated:
        return False
    if isinstance(parent, Proposal) and parent.proposal_type == "feedback":
        return is_parent_creator(user, parent) and parent.status == "pending_approval"
    return can_manage_parent_attachments(user, parent)
