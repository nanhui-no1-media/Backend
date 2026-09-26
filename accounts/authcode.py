"""认证码通道服务（ADR-0020）：生成 / 归一化 / 兑换（事务主体）。

- 码形：12 位、31 个无歧义字符（A–Z 去 I/L/O，2–9 去 0/1），熵 ≈59bit（暴力枚举不可行）；
  输入归一化（去空格 / 连字符、转大写），字段留 32 位余量供未来「自定义码」。
- 兑换：单事务锁码行 → 校验 → 写兑换记录 + used_count+1 + authcode 通道 approved。
  过期 / 吊销 / 用尽只停**后续**兑换，不回溯已通过者；兑换记录 = 审计留底。
"""
import re
import secrets

from django.db import transaction
from django.utils import timezone

from .models import AuthCode, AuthCodeRedemption, Verification

AUTHCODE_LENGTH = 12
# 31 个无歧义字符：A–Z 去 I/L/O；数字 2–9 去 0/1。
AUTHCODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

_NORMALIZE_RE = re.compile(r"[\s\-]")


class AuthCodeError(Exception):
    """兑换失败（文案直接面向用户）。"""


def generate_authcode_value() -> str:
    """生成一个 12 位随机码（后台新增表单预填用）。"""
    return "".join(secrets.choice(AUTHCODE_ALPHABET) for _ in range(AUTHCODE_LENGTH))


def normalize_authcode(raw: str | None) -> str:
    """归一化输入：去空格 / 连字符、转大写（兑换与后台存码共用）。"""
    return _NORMALIZE_RE.sub("", (raw or "")).upper()


def redeem_authcode(user, raw_code: str) -> AuthCode:
    """成员兑换认证码：成功写 authcode 通道 approved；失败抛 AuthCodeError。

    不变量：used_count 与兑换记录在同一事务内一致推进；used_count ≤ max_uses；
    每账号至多一条兑换记录（模型唯一约束兜底）。
    """
    normalized = normalize_authcode(raw_code)
    if not normalized:
        raise AuthCodeError("请输入认证码。")

    with transaction.atomic():
        code = AuthCode.objects.select_for_update().filter(code=normalized).first()
        if code is None:
            raise AuthCodeError("认证码无效。")
        if code.revoked_at is not None:
            raise AuthCodeError("认证码已被吊销。")
        now = timezone.now()
        if code.expires_at <= now:
            raise AuthCodeError("认证码已过期。")
        if code.used_count >= code.max_uses:
            raise AuthCodeError("认证码已用尽。")
        if AuthCodeRedemption.objects.filter(user=user).exists():
            # 每账号至多一次（顺序防线；唯一约束兜底并发）
            raise AuthCodeError("账号已完成验证，无需使用认证码。")

        AuthCodeRedemption.objects.create(authcode=code, user=user)
        code.used_count += 1
        code.save(update_fields=["used_count"])
        Verification.objects.update_or_create(
            user=user,
            channel=Verification.CHANNEL_AUTHCODE,
            defaults={
                "status": Verification.STATUS_APPROVED,
                "identifier": code.code,  # 码原文入库：后台可读，供追溯
                "verified_at": now,
                "verified_by": code.created_by,  # 发码人 = 担保人（留痕）
            },
        )
    return code
