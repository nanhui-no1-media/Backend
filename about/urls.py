from django.urls import path

from .views import AboutPageView

urlpatterns = [
    path("", AboutPageView.as_view(), name="about-detail"),
]
