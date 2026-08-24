from rest_framework.throttling import AnonRateThrottle

from common.policy import get_policy


class FeedbackAnonThrottle(AnonRateThrottle):
    """匿名意见反馈/举报节流：每个 IP 每天 N 条（N 来自 get_policy()）。

    继承 AnonRateThrottle —— 仅对未登录（匿名）请求按 IP 计数；
    已登录用户不计入（submit_feedback 本就面向匿名场景）。
    """

    scope = "feedback_anon"

    def get_rate(self):
        return f"{get_policy().feedback_anon_per_ip_per_day}/day"
