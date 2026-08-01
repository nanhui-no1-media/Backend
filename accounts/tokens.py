from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """邮箱验证令牌（#29 verify-email / resend 用；#28 register 发信时生成）。

    复用 PasswordResetTokenGenerator 模式（带时间戳、SECRET_KEY 签名、默认 7 天过期）。
    _make_hash_value 绑定 user.email + email_verified：
      - 改邮箱 → 旧令牌失效（须重新验证新邮箱）；
      - 验证成功后 email_verified 翻 True → 令牌随即失效，不可重放。
    """

    def _make_hash_value(self, user, timestamp):
        profile = getattr(user, "profile", None)
        email_verified = "1" if (profile and profile.email_verified) else "0"
        return f"{user.pk}{user.email}{email_verified}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
