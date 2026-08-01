"""Cloudflare Turnstile 服务端校验（自助注册人机校验，#28）。

DEBUG 或未配 TURNSTILE_SECRET_KEY 时跳过校验（本地不联网即可测注册流程）。
sitekey 公开（前端常量），secret 走 .env。
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token, remote_ip=""):
    """校验 Turnstile token。返回 True 表示通过（或已跳过）。"""
    # 本地开发 / 未配 secret → 跳过：便于不联网测试注册流程。
    if settings.DEBUG or not settings.TURNSTILE_SECRET_KEY:
        return True
    if not token:
        return False
    data = urllib.parse.urlencode(
        {
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": token,
            "remoteip": remote_ip or "",
        }
    ).encode()
    req = urllib.request.Request(SITEVERIFY_URL, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — 受信 URL
            result = json.loads(resp.read().decode())
            return bool(result.get("success"))
    except (urllib.error.URLError, OSError, ValueError):
        # 网络故障 / 解析失败 → 视为未通过（不因网络抖动放行机器人）。
        return False
