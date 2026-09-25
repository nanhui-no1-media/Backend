"""内置投递通道：站内 / 邮件 / Webhook（预留）/ 短信（预留）。"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from .registry import BaseChannel, get_source, register_channel

logger = logging.getLogger(__name__)


@register_channel
class SiteChannel(BaseChannel):
    """站内：通知在 dispatch 时已落库并 push；本通道不做额外投递。"""

    key = "site"
    name = "站内"
    description = "站内通知列表与未读提醒"

    def deliver(self, delivery) -> None:
        return None


@register_channel
class EmailChannel(BaseChannel):
    """邮件：发送通知摘要到用户已验证邮箱。"""

    key = "email"
    name = "邮件"
    description = "将通知摘要发送到邮箱（需已完成验证）"

    def is_available(self, user) -> bool:
        from accounts.models import is_verified

        email = (getattr(user, "email", None) or "").strip()
        if not email:
            return False
        try:
            return bool(is_verified(user))
        except Exception:  # pragma: no cover - 防御性
            return False

    def deliver(self, delivery) -> None:
        notification = delivery.notification
        user = notification.recipient
        email = (getattr(user, "email", None) or "").strip()
        if not email:
            raise ValueError("用户没有可用邮箱")

        source = get_source(notification.category)
        source_name = source.name if source else "站内"
        subject = f"{source_name}通知 - 南汇一中传媒社"

        parts = [f"你有一条新通知（{notification.event}）。"]
        link = (notification.payload or {}).get("url")
        if link:
            parts.append(f"详情：{link}")
        parts.append("请登录站点查看完整内容。")

        send_mail(
            subject=subject,
            message="\n".join(parts),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[email],
            fail_silently=False,
        )


@register_channel
class WebhookChannel(BaseChannel):
    """Webhook：向用户配置的 URL POST 通知载荷（P2 实现投递）。"""

    key = "webhook"
    name = "Webhook"
    description = "将通知 JSON POST 到自定义 URL（即将支持）"

    def is_available(self, user) -> bool:
        return False

    def deliver(self, delivery) -> None:
        raise NotImplementedError("Webhook 通道尚未开放")


@register_channel
class SmsChannel(BaseChannel):
    """短信：留接口，待服务商选型。"""

    key = "sms"
    name = "短信"
    description = "短信通知（即将支持）"

    def is_available(self, user) -> bool:
        return False

    def deliver(self, delivery) -> None:
        raise NotImplementedError("短信通道尚未接入服务商")
