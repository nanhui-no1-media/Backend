"""评论区 / 私信 / 通知 / 禁言 / 横幅 — 其它 app 只碰本模块，不 import 模型或 viewset。

写入规则（验证、全站禁言、评论区状态、嵌套上限、3 分钟撤回、墓碑删除）都收在这里。
HTTP 是事实源；``push_user`` / ``push_thread`` 只是推送适配器（Channels 未接线时静默 no-op）。
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from common.policy import get_policy
from reviews.visibility import visible_queryset

from .models import (
    Banner,
    Comment,
    CommentThread,
    Conversation,
    Message,
    Notification,
    UserMute,
)

logger = logging.getLogger(__name__)

RETRACT_WINDOW = timedelta(minutes=3)
MENTION_RE = re.compile(r"@(\w+)")

_HOST_MANAGE_PERM = {
    "news": "news.add_news",
    "activity": "activities.change_activity",
    "task": "tasks.manage_tasks",
}
_EMAIL_PREF = {
    Notification.CATEGORY_COMMENT: "email_notify_comment",
    Notification.CATEGORY_REVIEW: "email_notify_review",
    Notification.CATEGORY_DISCIPLINE: "email_notify_discipline",
}
_EMAIL_SUBJECT = {
    Notification.CATEGORY_COMMENT: "评论通知 - 南汇一中传媒社",
    Notification.CATEGORY_REVIEW: "审核通知 - 南汇一中传媒社",
    Notification.CATEGORY_DISCIPLINE: "纪律通知 - 南汇一中传媒社",
}


class MessagingError(Exception):
    """领域规则失败。视图映射 ``status`` → HTTP。"""

    status = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class MessagingForbidden(MessagingError):
    status = 403


class MessagingNotFound(MessagingError):
    status = 404


# ---- 宿主 / 评论区 -------------------------------------------------------

def host_of(thread: CommentThread):
    if thread.news_id:
        return thread.news
    if thread.activity_id:
        return thread.activity
    if thread.task_id:
        return thread.task
    raise MessagingError("评论区没有宿主")


def thread_for(host) -> CommentThread:
    """取或建该宿主上恰好一条评论区（默认开放）。"""
    field = host._meta.model_name
    if field not in ("news", "activity", "task"):
        raise MessagingError("评论区只能挂在新闻、活动或任务上")
    thread, _created = CommentThread.objects.get_or_create(
        **{field: host},
        defaults={"status": CommentThread.STATUS_OPEN},
    )
    return thread


def can_see_host(user, host) -> bool:
    """谁能看见宿主，谁就能看见其评论区（未公开的新闻评论区不对公众开放）。"""
    name = host._meta.model_name
    authenticated = bool(user and getattr(user, "is_authenticated", False))
    if name == "news":
        from news.models import News

        qs = News.objects.filter(pk=host.pk)
        visible = visible_queryset(qs, user, "news", action="retrieve")
        if not authenticated:
            return visible.filter(is_published=True).exists()
        if user.has_perm("reviews.moderate"):
            return visible.exists()
        return visible.filter(Q(is_published=True) | Q(author=user)).exists()
    if name == "activity":
        from activities.models import Activity

        qs = Activity.objects.filter(pk=host.pk)
        if not authenticated:
            return visible_queryset(qs, user, "activity", action="list").filter(
                type="survey", audience="public",
            ).exists()
        return visible_queryset(qs, user, "activity", action="retrieve").exists()
    if name == "task":
        return authenticated
    return False


def can_manage_thread(user, thread: CommentThread) -> bool:
    """宿主主人 **或** 宿主管理权限 **或** ``messaging.manage_comment_thread``。

    任务协管不含负责人/协作者——他们不能改任务评论区状态。
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.has_perm("messaging.manage_comment_thread"):
        return True
    host = host_of(thread)
    owner_id = _host_owner_id(host)
    if owner_id is not None and owner_id == user.pk:
        return True
    perm = _HOST_MANAGE_PERM.get(host._meta.model_name)
    return bool(perm and user.has_perm(perm))


def can_see_thread(user, thread: CommentThread) -> bool:
    """彻底关闭后普通读者看不到该区；协管仍可看。"""
    if not can_see_host(user, host_of(thread)):
        return False
    if thread.status == CommentThread.STATUS_CLOSED:
        return can_manage_thread(user, thread)
    return True


def set_thread_status(thread: CommentThread, user, status: str) -> CommentThread:
    if not can_manage_thread(user, thread):
        raise MessagingForbidden("没有管理该评论区的权限")
    allowed = {
        CommentThread.STATUS_OPEN,
        CommentThread.STATUS_MUTED,
        CommentThread.STATUS_CLOSED,
    }
    if status not in allowed:
        raise MessagingError("状态须为 open、muted 或 closed")
    thread.status = status
    thread.save(update_fields=["status"])
    return thread


def post_comment(thread: CommentThread, author, content: str, *, parent: Comment | None = None) -> Comment:
    content = (content or "").strip()
    if not content:
        raise MessagingError("评论内容不能为空")
    if not can_see_thread(author, thread):
        raise MessagingNotFound("评论区不存在")
    if thread.status == CommentThread.STATUS_MUTED:
        raise MessagingError("评论区已禁言")
    if thread.status != CommentThread.STATUS_OPEN:
        raise MessagingError("评论区已关闭")
    if is_muted(author):
        raise MessagingForbidden("你已被全站禁言，暂时不能发言")
    if parent is not None:
        if parent.thread_id != thread.pk:
            raise MessagingError("父评论不属于该评论区")
        depth = _depth(parent) + 1
    else:
        depth = 1
    cap = get_policy().comment_max_depth
    if depth > cap:
        raise MessagingError("超过最大嵌套层数")

    comment = Comment.objects.create(
        thread=thread, author=author, parent=parent, content=content,
    )
    push_thread(thread.pk, "comment", {
        "thread_id": thread.pk, "comment_id": comment.pk,
    })
    _notify_comment(comment, author, parent)
    return comment


def retract_comment(comment: Comment, user) -> Comment:
    if comment.author_id != user.pk:
        raise MessagingForbidden("只能撤回自己的评论")
    if comment.deleted_at:
        raise MessagingError("评论已删除")
    if comment.retracted_at:
        raise MessagingError("评论已撤回")
    if comment.replies.exists():
        raise MessagingError("已有回复，不能撤回")
    if timezone.now() - comment.created_at > RETRACT_WINDOW:
        raise MessagingError("已超过撤回时限")
    comment.retracted_at = timezone.now()
    comment.save(update_fields=["retracted_at", "updated_at"])
    push_thread(comment.thread_id, "comment", {
        "thread_id": comment.thread_id, "comment_id": comment.pk, "retracted": True,
    })
    return comment


def delete_comment(comment: Comment, user) -> Comment:
    if not can_manage_thread(user, comment.thread):
        raise MessagingForbidden("没有管理该评论区的权限")
    if comment.deleted_at:
        raise MessagingError("评论已删除")
    comment.deleted_at = timezone.now()
    comment.deleted_by = user
    comment.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
    push_thread(comment.thread_id, "comment", {
        "thread_id": comment.thread_id, "comment_id": comment.pk, "deleted": True,
    })
    return comment


# ---- 全站禁言 ------------------------------------------------------------

def current_mute(user) -> UserMute | None:
    """最新一条仍生效的禁言；顺带惰性解除已到期的。无则 ``None``。"""
    if not user or not getattr(user, "is_authenticated", False) or not getattr(user, "pk", None):
        return None
    _expire_mutes(user)
    return _active_mute(user)


def is_muted(user) -> bool:
    return current_mute(user) is not None


def mute_user(actor, user, *, reason: str = "", ends_at=None) -> UserMute:
    if not actor.has_perm("messaging.mute_user"):
        raise MessagingForbidden("没有全站禁言权限")
    if actor.pk == user.pk:
        raise MessagingError("不能禁言自己")
    if is_muted(user):
        raise MessagingError("该用户已被禁言")
    now = timezone.now()
    if ends_at is not None and ends_at <= now:
        raise MessagingError("结束时间须晚于当前时间")
    row = UserMute.objects.create(
        user=user,
        muted_by=actor,
        reason=reason or "",
        starts_at=now,
        ends_at=ends_at,
    )
    notify(
        user, Notification.CATEGORY_DISCIPLINE, "muted",
        actor=actor,
        payload={
            "mute_id": row.pk,
            "reason": row.reason,
            "ends_at": ends_at.isoformat() if ends_at else None,
        },
    )
    return row


def lift_mute(actor, user) -> UserMute:
    if not actor.has_perm("messaging.mute_user"):
        raise MessagingForbidden("没有全站禁言权限")
    row = current_mute(user)
    if row is None:
        raise MessagingError("该用户未被禁言")
    row.lifted_at = timezone.now()
    row.save(update_fields=["lifted_at"])
    notify(
        user, Notification.CATEGORY_DISCIPLINE, "mute_lifted",
        actor=actor,
        payload={"mute_id": row.pk},
    )
    return row


# ---- 通知 / 横幅 / 推送 ---------------------------------------------------

def notify(recipient, category: str, event: str, *, actor=None, payload: Mapping | None = None) -> Notification:
    """落库 + 可选邮件（偏好开且有绑定邮箱）+ ``user_{id}`` 推送。"""
    if category not in _EMAIL_PREF:
        raise MessagingError("通知类别须为 comment、review 或 discipline")
    data = dict(payload or {})
    if actor is not None:
        data.setdefault("actor_id", actor.pk)
        data.setdefault("actor_username", actor.username)
    row = Notification.objects.create(
        recipient=recipient,
        category=category,
        event=event,
        payload=data,
    )
    _maybe_email(recipient, category, event, data)
    push_user(recipient.pk, "notification", {
        "notification_id": row.pk, "category": category, "event": event,
    })
    return row


def current_banner(now=None) -> Banner | None:
    """当前窗口内至多一条：priority 高者胜，并列取较新。"""
    now = now or timezone.now()
    return (
        Banner.objects
        .filter(starts_at__lte=now, ends_at__gt=now)
        .order_by("-priority", "-created_at")
        .first()
    )


def push_user(user_id, event: str, payload: Mapping | None = None) -> None:
    _group_send(f"user_{user_id}", event, payload)


def push_thread(thread_id, event: str, payload: Mapping | None = None) -> None:
    _group_send(f"thread_{thread_id}", event, payload)


# ---- 私信（1:1） ---------------------------------------------------------

def start_private(user, target) -> tuple[Conversation, bool]:
    """返回 ``(conversation, created)``。"""
    if target.pk == user.pk:
        raise MessagingError("不能和自己对话")
    from accounts.models import is_verified

    if not is_verified(target):
        raise MessagingError("对方尚未完成验证")
    if is_muted(user):
        raise MessagingForbidden("你已被全站禁言，暂时不能发言")
    existing = (
        Conversation.objects
        .filter(participants=user)
        .filter(participants=target)
        .first()
    )
    if existing:
        return existing, False
    conversation = Conversation.objects.create()
    conversation.participants.set([user, target])
    return conversation, True


def send_dm(conversation: Conversation, sender, content: str) -> Message:
    content = (content or "").strip()
    if not content:
        raise MessagingError("消息内容不能为空")
    if not conversation.participants.filter(pk=sender.pk).exists():
        raise MessagingForbidden("不是该会话的参与者")
    if is_muted(sender):
        raise MessagingForbidden("你已被全站禁言，暂时不能发言")
    message = Message.objects.create(
        conversation=conversation, sender=sender, content=content,
    )
    mentioned = _mentioned_users(content)
    if mentioned:
        message.mentions.set(mentioned)
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
    for uid in conversation.participants.exclude(pk=sender.pk).values_list("id", flat=True):
        push_user(uid, "dm", {
            "conversation_id": conversation.pk, "message_id": message.pk,
        })
    return message


def retract_dm(message: Message, user) -> Message:
    if message.sender_id != user.pk:
        raise MessagingForbidden("只能撤回自己的消息")
    if message.retracted_at:
        raise MessagingError("消息已撤回")
    if timezone.now() - message.created_at > RETRACT_WINDOW:
        raise MessagingError("已超过撤回时限")
    message.retracted_at = timezone.now()
    message.save(update_fields=["retracted_at", "updated_at"])
    for uid in message.conversation.participants.exclude(pk=user.pk).values_list("id", flat=True):
        push_user(uid, "dm", {
            "conversation_id": message.conversation_id,
            "message_id": message.pk,
            "retracted": True,
        })
    return message


# ---- 内部 ---------------------------------------------------------------

def _host_owner_id(host):
    name = host._meta.model_name
    if name == "news":
        return host.author_id
    if name in ("activity", "task"):
        return host.creator_id
    return None


def _depth(comment: Comment) -> int:
    depth = 1
    current = comment
    seen: set[int] = set()
    while current.parent_id:
        if current.pk in seen:
            break
        seen.add(current.pk)
        current = current.parent
        depth += 1
    return depth


def _mentioned_users(content: str) -> list[User]:
    names = MENTION_RE.findall(content)
    if not names:
        return []
    return list(User.objects.filter(username__in=names, is_active=True))


def _notify_comment(comment: Comment, author, parent: Comment | None) -> None:
    host = host_of(comment.thread)
    payload = {
        "comment_id": comment.pk,
        "thread_id": comment.thread_id,
        "parent_id": parent.pk if parent else None,
        "news_id": comment.thread.news_id,
        "activity_id": comment.thread.activity_id,
        "task_id": comment.thread.task_id,
    }
    seen: set[int] = {author.pk}
    if parent is not None and parent.author_id not in seen:
        notify(
            parent.author, Notification.CATEGORY_COMMENT, "comment_replied",
            actor=author, payload=payload,
        )
        seen.add(parent.author_id)
    for mentioned in _mentioned_users(comment.content):
        if mentioned.pk in seen:
            continue
        if not can_see_host(mentioned, host):
            continue
        notify(
            mentioned, Notification.CATEGORY_COMMENT, "comment_mentioned",
            actor=author, payload=payload,
        )
        seen.add(mentioned.pk)


def _active_mute(user, *, now=None) -> UserMute | None:
    now = now or timezone.now()
    return (
        UserMute.objects
        .filter(user=user, lifted_at__isnull=True)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .order_by("-starts_at")
        .first()
    )


def _expire_mutes(user) -> None:
    now = timezone.now()
    expired = list(
        UserMute.objects.filter(
            user=user, lifted_at__isnull=True, ends_at__isnull=False, ends_at__lte=now,
        )
    )
    for row in expired:
        row.lifted_at = now
        row.save(update_fields=["lifted_at"])
        notify(
            user, Notification.CATEGORY_DISCIPLINE, "mute_expired",
            actor=None,
            payload={"mute_id": row.pk},
        )


def _maybe_email(recipient, category: str, event: str, payload: dict) -> None:
    email = (getattr(recipient, "email", None) or "").strip()
    if not email:
        return
    try:
        profile = recipient.profile
    except (ObjectDoesNotExist, AttributeError):
        return
    pref = _EMAIL_PREF.get(category)
    if not pref or not getattr(profile, pref, False):
        return
    subject = _EMAIL_SUBJECT.get(category, "通知 - 南汇一中传媒社")
    try:
        send_mail(
            subject=subject,
            message=f"你有一条新通知（{event}）。请登录站点查看。",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("发送通知邮件失败: user_pk=%s event=%s", recipient.pk, event)


def _group_send(group: str, event: str, payload: Mapping | None) -> None:
    """Channels 未安装 / 未配置 / 发送失败时静默。type=messaging.event 供 consumer 收。"""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return
    try:
        layer = get_channel_layer()
    except Exception:
        return
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            group,
            {"type": "messaging.event", "event": event, "payload": dict(payload or {})},
        )
    except Exception:
        logger.debug("channel layer group_send failed group=%s event=%s", group, event, exc_info=True)
