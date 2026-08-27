"""署名反馈处理结果：经 messaging.services.notify 投给提交者。

匿名反馈无 creator，不通知。提交/撤回不建会话、不发通知——社长从反馈列表跟进。
"""
from django.contrib.auth.models import User

from messaging.services import notify

_RESULT_EVENTS = {"approved": "approved", "rejected": "rejected"}


def proposal_approvers():
    """所有「持有 approve_proposal 权限」的活跃用户（含非社长组直接授权者）。"""
    return list(User.objects.filter(
        is_active=True,
        groups__permissions__codename="approve_proposal",
        groups__permissions__content_type__app_label="proposals",
    ).distinct())


def notify_proposal_event(proposal, event, *, actor, reason=""):
    """署名反馈的处理结果通知提交者。非结果事件或匿名提交则 no-op。"""
    if proposal.creator_id is None:
        return
    if event not in _RESULT_EVENTS:
        return
    payload = {
        "type": "proposal",
        "id": proposal.pk,
        "url": f"/feedback/{proposal.pk}",
    }
    if reason:
        payload["reason"] = reason
    notify(
        proposal.creator,
        "review",
        _RESULT_EVENTS[event],
        actor=actor,
        payload=payload,
    )
