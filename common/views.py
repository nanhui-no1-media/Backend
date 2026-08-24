from dataclasses import asdict

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .policy import get_policy


class SitePolicyView(APIView):
    """Public snapshot of operational knobs for the SPA. No write path."""

    permission_classes = [AllowAny]
    authentication_classes = []  # anonymous GET; skip session/CSRF dance

    def get(self, request):
        return Response(asdict(get_policy()))
