from django.db import models


class SingletonManager(models.Manager):
    """单例管理器：get_solo() 始终返回唯一的那一行（缺失则按默认值创建）。"""

    def get_solo(self):
        obj, _ = self.get_or_create(pk=1, defaults={"title": "关于我们"})
        return obj


class AboutPage(models.Model):
    """站点「关于我们」页：全局单例（pk 恒为 1），站长可随时编辑、保存即发布。"""

    title = models.CharField("标题", max_length=200, default="关于我们")
    content = models.TextField("正文（HTML）", blank=True, default="")
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    objects = SingletonManager()

    class Meta:
        verbose_name = verbose_name_plural = "关于页"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # 单例约束：任何写入都落到 pk=1；若已存在则降级为更新，避免 INSERT 主键冲突。
        self.pk = 1
        if self._state.adding and AboutPage.objects.filter(pk=1).exists():
            self._state.adding = False
            # Manager.create() 会强制 force_insert=True，已存在时需移除以走 UPDATE。
            kwargs.pop("force_insert", None)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 禁止删除单例，保证「关于」页永不消失（页面永不 404）。
        pass
