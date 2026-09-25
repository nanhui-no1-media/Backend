"""分发流水线：业务事件 → 站内落库 + 实时 push + 订阅匹配 → 外发通道同步投递。"""
from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping

from django.db import transaction
from django.utils import timezone

from ..models import Notification, NotificationDelivery, NotificationSubscription
from .registry import all_channels, get_channel, get_source

logger = logging.getLogger(__name__)


def dispatch(
    source_key: str,
    event: str,
    recipients: Iterable,
    *,
    actor=None,
    payload: Mapping | None = None,
) -> list:
    """统一分发入口。

    - 站内：每条落库（Notification）并实时 push；
    - 外发：按用户订阅（惰性默认）为启用的通道创建 NotificationDelivery，
      并同步投递（失败留痕、不自动重试；在事务中调用时挂到提交后执行，
      避免「邮件已发、数据回滚」的幽灵通知）。
    """
    if get_source(source_key) is None:
        raise ValueError(f"未知通知源：{source_key}")
    data = dict(payload or {})
    if actor is not None:
        data.setdefault("actor_id", getattr(actor, "pk", None))
        data.setdefault("actor_username", getattr(actor, "username", ""))

    rows: list = []
    for user in recipients:
        row = Notification.objects.create(
            recipient=user,
            category=source_key,
            event=event,
            payload=data,
        )
        _push(row)
        _deliver(row)
        rows.append(row)
    return rows


def subscribed_channels(user, source_key: str) -> list:
    """用户在某源上启用的通道列表（缺行回退到源定义 default_channels）。"""
    source = get_source(source_key)
    defaults = set(source.default_channels) if source else {"site"}
    rows = dict(
        NotificationSubscription.objects
        .filter(user=user, source_key=source_key)
        .values_list("channel_key", "enabled")
    )
    result = []
    for channel in all_channels():
        enabled = rows.get(channel.key, channel.key in defaults)
        if enabled:
            result.append(channel.key)
    return result


def deliver(delivery: NotificationDelivery) -> bool:
    """同步投递单条投递行：成功标 sent，失败标 failed 留痕。本函数不抛出。"""
    channel = get_channel(delivery.channel_key)
    delivery.attempts = (delivery.attempts or 0) + 1
    if channel is None:
        delivery.status = NotificationDelivery.STATUS_FAILED
        delivery.last_error = f"未知通道：{delivery.channel_key}"
        delivery.save(update_fields=["status", "last_error", "attempts"])
        return False
    try:
        channel.deliver(delivery)
    except Exception as exc:
        delivery.status = NotificationDelivery.STATUS_FAILED
        delivery.last_error = str(exc)[:500]
        delivery.save(update_fields=["status", "last_error", "attempts"])
        logger.warning(
            "通知投递失败 delivery=%s channel=%s: %s",
            delivery.pk, delivery.channel_key, exc,
        )
        return False
    delivery.status = NotificationDelivery.STATUS_SENT
    delivery.sent_at = timezone.now()
    delivery.last_error = ""
    delivery.save(update_fields=["status", "sent_at", "last_error", "attempts"])
    return True


def _push(row: Notification) -> None:
    """实时推送（Channels 未接线时静默）。"""
    try:
        from ..services import push_user

        push_user(row.recipient_id, "notification", {
            "notification_id": row.pk,
            "category": row.category,
            "event": row.event,
        })
    except Exception:  # pragma: no cover - 推送失败不影响通知落库
        logger.debug("notification push failed id=%s", row.pk, exc_info=True)


def _deliver(row: Notification) -> None:
    """为启用的外发通道建投递行并同步投递（站内已落库，跳过）。"""
    for key in subscribed_channels(row.recipient, row.category):
        if key == "site":
            continue
        channel = get_channel(key)
        if channel is None:
            continue
        try:
            available = channel.is_available(row.recipient)
        except Exception:  # pragma: no cover - 防御性
            available = False
        if not available:
            continue
        delivery = NotificationDelivery.objects.create(
            notification=row,
            channel_key=key,
        )
        # 事务中调用时挂到提交后投递，避免「邮件已发、数据回滚」的幽灵通知。
        transaction.on_commit(lambda d=delivery: deliver(d))
