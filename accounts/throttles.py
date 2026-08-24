from rest_framework.throttling import SimpleRateThrottle

from common.policy import get_policy


class _IPLimitThrottle(SimpleRateThrottle):
    """按 IP 计数的限流基类（用于函数式视图：手动实例化 + allow_request）。

    SimpleRateThrottle 的 get_cache_key 是抽象的，须覆写；这里固定用 self.scope +
    请求方 IP 作缓存键（与 DRF 内置 AnonRateThrottle 同形），不依赖 view 实例。
    """

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class RegisterThrottle(_IPLimitThrottle):
    """自助注册节流：每个 IP 每天 N 次（N 来自 get_policy()）。"""

    scope = "register"

    def get_rate(self):
        return f"{get_policy().register_per_ip_per_day}/day"


class ResendVerificationThrottle(_IPLimitThrottle):
    """重发邮箱验证邮件节流：每个 IP 每小时 N 次（N 来自 get_policy()）。"""

    scope = "resend_verification"

    def get_rate(self):
        return f"{get_policy().resend_verification_per_ip_per_hour}/hour"
