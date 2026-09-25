"""通知投递 worker。

用法：
    python manage.py notification_worker            # 常驻循环（默认 5s 一轮）
    python manage.py notification_worker --once     # 处理一轮后退出（cron / 测试）

部署：systemd 常驻或 cron 拉起；NotificationDelivery 即持久队列。
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import models as db_models
from django.utils import timezone

from messaging.models import NotificationDelivery
from messaging.notifications.registry import get_channel

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BATCH_SIZE = 50
RETRY_CAP_SECONDS = 3600


class Command(BaseCommand):
    help = "通知投递 worker：轮询 NotificationDelivery 队列并投递外发通道"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="只处理一轮后退出")
        parser.add_argument("--interval", type=float, default=5.0, help="常驻模式轮询间隔（秒）")

    def handle(self, *args, **options):
        if options["once"]:
            processed = self._process_batch()
            self.stdout.write(f"processed {processed}")
            return
        self.stdout.write(self.style.SUCCESS("notification_worker started (Ctrl-C to stop)"))
        try:
            while True:
                try:
                    self._process_batch()
                except Exception:  # pragma: no cover - 守护循环不因单轮错误退出
                    logger.exception("notification_worker 批次异常")
                time.sleep(options["interval"])
        except KeyboardInterrupt:  # pragma: no cover
            self.stdout.write("notification_worker stopped")

    # ---- 内部 ----

    def _process_batch(self) -> int:
        now = timezone.now()
        qs = (
            NotificationDelivery.objects
            .filter(status__in=[NotificationDelivery.STATUS_PENDING, NotificationDelivery.STATUS_FAILED])
            .filter(db_models.Q(next_retry_at__isnull=True) | db_models.Q(next_retry_at__lte=now))
            .select_related("notification", "notification__recipient")
            .order_by("created_at")[:BATCH_SIZE]
        )
        processed = 0
        for delivery in qs:
            self._deliver_one(delivery)
            processed += 1
        return processed

    def _deliver_one(self, delivery: NotificationDelivery) -> None:
        channel = get_channel(delivery.channel_key)
        if channel is None:
            delivery.status = NotificationDelivery.STATUS_FAILED
            delivery.last_error = f"未知通道：{delivery.channel_key}"
            delivery.next_retry_at = None
            delivery.save(update_fields=["status", "last_error", "next_retry_at"])
            return

        delivery.attempts += 1
        try:
            channel.deliver(delivery)
        except Exception as exc:
            delivery.status = NotificationDelivery.STATUS_FAILED
            delivery.last_error = str(exc)[:500]
            if delivery.attempts >= MAX_ATTEMPTS:
                delivery.next_retry_at = None  # 死信：停止自动重试
            else:
                delay = min(2 ** delivery.attempts, RETRY_CAP_SECONDS)
                delivery.next_retry_at = timezone.now() + timedelta(seconds=delay)
            delivery.save(update_fields=["status", "last_error", "next_retry_at", "attempts"])
        else:
            delivery.status = NotificationDelivery.STATUS_SENT
            delivery.sent_at = timezone.now()
            delivery.last_error = ""
            delivery.save(update_fields=["status", "sent_at", "last_error", "attempts"])
