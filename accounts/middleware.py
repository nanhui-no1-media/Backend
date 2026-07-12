from django.http import JsonResponse

from .models import UserSession
from .utils import record_user_session


class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            session_key = request.session.session_key
            current = (
                UserSession.objects
                .filter(user=user, is_current=True)
                .order_by("-created_at")
                .first()
            )
            if current is None:
                # Session that predates this feature: adopt it as the current one
                if session_key:
                    record_user_session(request, user, session_key)
            elif current.session_key != session_key:
                # Another device logged in → this session is superseded
                request.session.flush()
                return JsonResponse(
                    {
                        "detail": "您的账号在其他设备登录，您已被迫下线。",
                        "reason": "session_superseded",
                        "takeover": {
                            "device_name": current.device_name,
                            "device_type": current.device_type,
                            "ip": current.ip_address,
                            "time": current.created_at.isoformat(),
                        },
                    },
                    status=401,
                )
        return self.get_response(request)
