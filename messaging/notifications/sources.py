"""首批通知源定义（注册即生效，见 messaging.apps.ready）。"""
from .registry import Event, NotificationSource, register_source


@register_source
class ReviewSource(NotificationSource):
    key = "review"
    name = "审核系统"
    description = "作品审核结果、举报处理结果"
    events = (
        Event("approved", "审核通过"),
        Event("rejected", "审核驳回"),
        Event("changes_requested", "需要修改"),
        Event("report_resolved", "举报处理结果"),
        Event("feedback_replied", "反馈回复"),
    )
    default_channels = ("site",)


@register_source
class ActivitySource(NotificationSource):
    key = "activity"
    name = "活动生命周期"
    description = "活动发布、报名开放、时间变更、取消、截止提醒"
    events = (
        Event("published", "活动发布"),
        Event("registration_open", "报名开放"),
        Event("updated", "信息变更"),
        Event("cancelled", "活动取消"),
        Event("deadline_soon", "即将截止"),
    )
    default_channels = ("site",)


@register_source
class CommentSource(NotificationSource):
    key = "comment"
    name = "评论回复"
    description = "有人回复了你的评论"
    events = (Event("reply", "评论回复"),)
    default_channels = ("site",)


@register_source
class DmSource(NotificationSource):
    key = "dm"
    name = "私信"
    description = "收到新私信（站内提示，不复制内容）"
    events = (Event("new_message", "新私信"),)
    default_channels = ("site",)


@register_source
class AnnouncementSource(NotificationSource):
    key = "announcement"
    name = "横幅广播"
    description = "全站公告发布"
    events = (Event("published", "公告发布"),)
    default_channels = ("site",)


@register_source
class DisciplineSource(NotificationSource):
    key = "discipline"
    name = "纪律 / 处罚"
    description = "禁言生效、解除等纪律通知"
    events = (
        Event("muted", "禁言生效"),
        Event("mute_lifted", "禁言解除"),
        Event("mute_expired", "禁言到期"),
    )
    default_channels = ("site",)
