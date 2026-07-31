from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly

from .models import AboutPage
from .serializers import AboutPageSerializer


class AboutPageView(RetrieveUpdateAPIView):
    """GET /about/（公开）/ PUT /about/（需 about.change_aboutpage）。

    始终作用于单例：get_object 忽略 URL 参数，返回 AboutPage 唯一行。
    权限走 DRF 内置 DjangoModelPermissionsOrAnonReadOnly——GET（perms_map 为空）
    匿名可读，PUT 按 about.change_aboutpage 校验，与 news 一致（见角色→权限迁移设计）。
    """

    queryset = AboutPage.objects.all()
    serializer_class = AboutPageSerializer
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]

    def get_object(self):
        return AboutPage.objects.get_solo()
