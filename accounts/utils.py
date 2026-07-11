import re

from django.db import transaction

from .models import UserSession


_BOT_RE = re.compile(r"bot|crawl|spider|slurp|fetcher", re.I)
_TABLET_RE = re.compile(r"iPad|Android(?!.*Mobile)|Silk|Kindle|PlayBook", re.I)
_MOBILE_RE = re.compile(r"Android|iPhone|iPod|Mobile|Windows Phone|BlackBerry", re.I)
_BROWSER_RE = re.compile(r"(Edge|Edg|OPR|Opera|Chrome|Chromium|Firefox|Safari|MSIE|Trident)[/ ]([\d.]+)")
_OS_RE = re.compile(r"(Windows NT|Windows \w+|Mac OS X|iPhone OS|Android|Linux)")


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR")


def parse_user_agent(ua):
    if not ua:
        return "Unknown", ""
    if _BOT_RE.search(ua):
        device_type = "Bot"
    elif _TABLET_RE.search(ua):
        device_type = "Tablet"
    elif _MOBILE_RE.search(ua):
        device_type = "Mobile"
    else:
        device_type = "Desktop"

    browser = ""
    m = _BROWSER_RE.search(ua)
    if m:
        name = {"Edg": "Edge", "OPR": "Opera", "MSIE": "IE", "Trident": "IE"}.get(m.group(1), m.group(1))
        browser = name

    os_name = ""
    o = _OS_RE.search(ua)
    if o:
        raw = o.group(1)
        if raw.startswith("Windows"):
            os_name = "Windows"
        elif raw.startswith("Mac OS X"):
            os_name = "macOS"
        elif raw.startswith("iPhone OS"):
            os_name = "iOS"
        elif raw.startswith("Android"):
            os_name = "Android"
        elif raw.startswith("Linux"):
            os_name = "Linux"
        else:
            os_name = raw

    device_name = " · ".join(p for p in (browser, os_name) if p)
    return device_type, device_name


@transaction.atomic
def record_user_session(request, user, session_key):
    ip = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")
    device_type, device_name = parse_user_agent(ua)

    UserSession.objects.filter(user=user).update(is_current=False)
    UserSession.objects.update_or_create(
        session_key=session_key,
        defaults={
            "user": user,
            "ip_address": ip,
            "user_agent": ua,
            "device_type": device_type,
            "device_name": device_name,
            "is_current": True,
        },
    )
    UserSession.objects.filter(user=user, is_current=False).delete()
