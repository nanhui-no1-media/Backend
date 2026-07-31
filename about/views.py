from rest_framework.generics import RetrieveUpdateAPIView

from .models import AboutPage
from .permissions import AboutPagePermission
from .serializers import AboutPageSerializer


class AboutPageView(RetrieveUpdateAPIView):
    """GET /about/（公开）/ PUT /about/（需 about.change_aboutpage）。

    始终作用于单例：get_object 忽略 URL 参数，返回 AboutPage 唯一行。
    """

    serializer_class = AboutPageSerializer
    permission_classes = [AboutPagePermission]

    def get_object(self):
        return AboutPage.objects.get_solo()
