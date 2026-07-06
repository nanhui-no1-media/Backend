from rest_framework.throttling import AnonRateThrottle


class FeedbackAnonThrottle(AnonRateThrottle):
    """匿名意见反馈/举报节流：每个 IP 每天 10 条。

    继承 AnonRateThrottle —— 仅对未登录（匿名）请求按 IP 计数；
    已登录用户不计入（submit_feedback 本就面向匿名场景）。
    速率由 settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['feedback_anon'] 提供。
    """

    scope = "feedback_anon"
