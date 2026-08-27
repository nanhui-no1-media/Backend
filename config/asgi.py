"""
ASGI config for config project.

HTTP stays on Django; WebSocket is session-authenticated messaging push
(ADR 0015). ``get_asgi_application()`` runs before routing imports so the
app registry is ready when consumers touch the ORM.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from messaging.routing import websocket_urlpatterns


def _websocket_app(inner):
    """Apply origin check with current ALLOWED_HOSTS (Channels freezes the list at import)."""

    async def app(scope, receive, send):
        return await AllowedHostsOriginValidator(inner)(scope, receive, send)

    return app


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "lifespan": django_asgi_app,
    "websocket": _websocket_app(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
