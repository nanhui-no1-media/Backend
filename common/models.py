from django.db import models

from .policy import (
    DEFAULT_FEEDBACK_ANON_PER_IP_PER_DAY,
    DEFAULT_REGISTER_PER_IP_PER_DAY,
    DEFAULT_REGISTRATION_ENABLED,
    DEFAULT_RESEND_VERIFICATION_PER_IP_PER_HOUR,
    DEFAULT_SYNC_UPLOAD_MAX_BYTES,
    DEFAULT_TUS_MEDIA_MAX_BYTES,
    DEFAULT_VERIFICATION_ENABLED,
    invalidate_policy_cache,
)


class SiteSettings(models.Model):
    """Singleton operational knobs (pk always 1). Edit in Django admin."""

    verification_enabled = models.BooleanField(
        "验证通道开启",
        default=DEFAULT_VERIFICATION_ENABLED,
        help_text="关闭后不可新开或完成任何验证通道；已通过者仍算已验证。",
    )
    registration_enabled = models.BooleanField(
        "开放自助注册",
        default=DEFAULT_REGISTRATION_ENABLED,
        help_text="关闭后自助注册接口返回 403。",
    )
    register_per_ip_per_day = models.PositiveIntegerField(
        "每 IP 每日注册次数",
        default=DEFAULT_REGISTER_PER_IP_PER_DAY,
    )
    resend_verification_per_ip_per_hour = models.PositiveIntegerField(
        "每 IP 每小时重发验证邮件次数",
        default=DEFAULT_RESEND_VERIFICATION_PER_IP_PER_HOUR,
    )
    feedback_anon_per_ip_per_day = models.PositiveIntegerField(
        "每 IP 每日匿名反馈次数",
        default=DEFAULT_FEEDBACK_ANON_PER_IP_PER_DAY,
    )
    sync_upload_max_bytes = models.PositiveBigIntegerField(
        "同步上传单文件上限（字节）",
        default=DEFAULT_SYNC_UPLOAD_MAX_BYTES,
        help_text="任意类型走同步通路的上限；超过则仅图片/视频可走 tus。",
    )
    tus_media_max_bytes = models.PositiveBigIntegerField(
        "tus 图/视频上限（字节）",
        default=DEFAULT_TUS_MEDIA_MAX_BYTES,
    )

    class Meta:
        verbose_name = "站点策略"
        verbose_name_plural = "站点策略"

    def __str__(self):
        return "站点策略"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        invalidate_policy_cache()

    def delete(self, *args, **kwargs):
        return 0, {}
