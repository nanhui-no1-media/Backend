from dataclasses import asdict

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.turnstile import public_turnstile_fields

from .policy import get_policy


class SitePolicyView(APIView):
    """Public snapshot of operational knobs for the SPA. No write path."""

    permission_classes = [AllowAny]
    authentication_classes = []  # anonymous GET; skip session/CSRF dance

    def get(self, request):
        # Turnstile sitekey 来自 .env，不是 SiteSettings；叠到公开快照给 SPA。
        return Response({**asdict(get_policy()), **public_turnstile_fields()})
