"""访客问卷作答的设备标识（ADR 0014）。

浏览器没有稳定硬件 ID；门户生成 UUID 写入 localStorage，请求带 ``X-Device-Id``。
未登录作答按 (问卷, 设备标识) 一人一份，防公开问卷刷单。
"""
import re

from rest_framework.request import Request

DEVICE_ID_HEADER = "HTTP_X_DEVICE_ID"
DEVICE_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def device_id_from_request(request: Request) -> str:
    """读 ``X-Device-Id``；缺或非法返回空串。"""
    raw = (request.META.get(DEVICE_ID_HEADER) or "").strip()
    if not raw or not DEVICE_ID_RE.fullmatch(raw):
        return ""
    return raw.lower()
