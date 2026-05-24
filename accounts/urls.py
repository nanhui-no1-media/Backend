from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.me_view, name="me"),
    path("password-reset/", views.password_reset_view, name="password_reset"),
    path("password-reset/confirm/", views.password_reset_confirm_view, name="password_reset_confirm"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/update/", views.profile_update_view, name="profile_update"),
    path("profile/change-password/", views.change_password_view, name="change_password"),
    path("users/", views.users_view, name="users"),
]
