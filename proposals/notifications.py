"""申报事件通知：通过站内通信（messaging）给申报人和社长推送事件消息。

每个申报创建时即建立一个 type="proposal" 的会话，参与者 = 创建人 + 全体社长。
关键事件（提交/投票结束/通过/打回/拒绝/重新提交/撤回）在会话里发一条消息，
申报人和社长都能在「站内通信」里看到未读提醒。
"""
from django.contrib.auth.models import User

EVENT_TEXT = {
    "created_activity": "📌 新活动申报「{title}」已发起投票，请大家在 3 天内投票。",
    "created_feedback": "📌 新意见反馈「{title}」已提交，请社长审批。",
    "voting_ended": "⏰ 活动申报「{title}」投票已结束，进入待社长审批。",
    "approved": "✅ 申报「{title}」已由社长通过。",
    "returned": "↩️ 申报「{title}」已被社长打回，请修改后重新提交。理由：{reason}",
    "rejected": "❌ 申报「{title}」已由社长拒绝。理由：{reason}",
    "resubmitted": "🔄 申报「{title}」已重新提交。",
    "withdrawn": "🗑️ 申报「{title}」已被创建人撤回。",
}


def _proposal_approvers():
    """所有「持有 approve_proposal 权限」的活跃用户（含非社长组直接授权者）。"""
    return list(User.objects.filter(
        is_active=True,
        groups__permissions__codename="approve_proposal",
        groups__permissions__content_type__app_label="proposals",
    ).distinct())


def _ensure_conversation(proposal):
    """获取或创建申报会话，并补全参与者（创建人 + 全体社长）。"""
    from messaging.models import Conversation

    conversation, _ = Conversation.objects.get_or_create(
        conversation_type="proposal",
        proposal=proposal,
    )
    participant_ids = {proposal.creator_id}
    for p in _proposal_approvers():
        participant_ids.add(p.pk)
    conversation.participants.set(participant_ids)
    return conversation


def notify_proposal_event(proposal, event, *, actor, reason=""):
    """在申报会话中发布一条事件消息。

    - proposal: Proposal 实例
    - event: EVENT_TEXT 的 key
    - actor: 触发该事件的用户（消息发送者）
    - reason: 打回/拒绝理由
    """
    from messaging.models import Message

    template = EVENT_TEXT.get(event)
    if not template:
        return
    content = template.format(title=proposal.title, reason=reason)
    conversation = _ensure_conversation(proposal)
    Message.objects.create(conversation=conversation, sender=actor, content=content)
