from django.apps import AppConfig


class AttachmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "attachments"
    verbose_name = "统一附件"

    def ready(self):
        # 连接 post_delete 信号：删除附件行时同步回收磁盘文件（含父级级联删除）。
        from . import signals  # noqa: F401
