"""通知源定义（注册即生效，见 messaging.apps.ready）。

事件表必须与业务代码实际发出的 ``event`` 字符串一一对应（订阅粒度为源级，
事件用于展示；新增事件时两处同步修改）。
"""
from .registry import Event, NotificationSource, register_source


@register_source
class ReviewSource(NotificationSource):
    key = "review"
    name = "审核系统"
    description = "内容审核、举报与意见反馈处理、身份认证"
    color = "#0756a2"
    emoji = "🛡️"
    events = (
        # —— 待办：发给有处理权限的人（权限驱动投递）——
        Event("content_submitted", "新内容送审"),
        Event("feedback_submitted", "新意见反馈"),
        Event("report_submitted", "新举报"),
        Event("identity_submitted", "新认证申请"),
        # —— 结果：发给当事人 ——
        Event("approved", "内容审核通过"),
        Event("rejected", "内容审核驳回"),
        Event("removed", "内容已下架"),
        Event("closed", "意见反馈了结"),
        Event("report_resolved", "举报处理结果"),
        Event("identity_resolved", "认证审核结果"),
    )
    default_channels = ("site",)


@register_source
class ActivitySource(NotificationSource):
    key = "activity"
    name = "活动生命周期"
    description = "活动发布、到点开放"
    color = "#e8833a"
    emoji = "📅"
    events = (
        Event("published", "活动发布"),
        Event("opened", "活动开始"),
    )
    default_channels = ("site",)


@register_source
class CommentSource(NotificationSource):
    key = "comment"
    name = "评论回复"
    description = "有人回复了你的评论或提到了你"
    color = "#2e9e6b"
    emoji = "💬"
    events = (
        Event("comment_replied", "评论回复"),
        Event("comment_mentioned", "@ 提及"),
    )
    default_channels = ("site",)


@register_source
class DmSource(NotificationSource):
    key = "dm"
    name = "私信"
    description = "收到新私信（站内提示，不复制内容）"
    color = "#7c5cd6"
    emoji = "✉️"
    events = (Event("new_message", "新私信"),)
    default_channels = ("site",)


@register_source
class AnnouncementSource(NotificationSource):
    key = "announcement"
    name = "横幅广播"
    description = "全站公告发布"
    color = "#d99a1f"
    emoji = "📢"
    events = (Event("published", "公告发布"),)
    default_channels = ("site",)


@register_source
class DisciplineSource(NotificationSource):
    key = "discipline"
    name = "纪律 / 处罚"
    description = "禁言生效、解除等纪律通知"
    color = "#d64545"
    emoji = "⚖️"
    events = (
        Event("muted", "禁言生效"),
        Event("mute_lifted", "禁言解除"),
        Event("mute_expired", "禁言到期"),
    )
    default_channels = ("site",)
