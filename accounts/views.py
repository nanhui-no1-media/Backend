import json
from datetime import timedelta
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail

from .forms import LoginForm, PasswordResetForm, PasswordResetConfirmForm, ProfileForm, ChangePasswordForm
from .models import Profile, UserSession

LOGIN_PROTECTION_SECONDS = 600  # 登录保护窗口：登录后 10 分钟内他方新会话登录被拒


def _json_body(request):
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None


def _form_errors(form):
    errors = []
    for field_errors in form.errors.values():
        errors.extend(field_errors)
    for error in form.non_field_errors():
        errors.append(error)
    return errors[0] if len(errors) == 1 else errors


@require_POST
def login_view(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = LoginForm(body)
    if not form.is_valid():
        return JsonResponse({"error": _form_errors(form)}, status=400)

    username = form.get_username()
    if username is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    user = authenticate(request, username=username, password=form.cleaned_data["password"])
    if user is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    # 10 分钟登录保护：该账号已有当前会话且登录未满窗口、且非同一会话再认证 → 拒绝
    existing = UserSession.objects.filter(user=user, is_current=True).first()
    if existing:
        age = timezone.now() - existing.created_at
        same_session = existing.session_key == request.session.session_key
        if not same_session and age < timedelta(seconds=LOGIN_PROTECTION_SECONDS):
            retry_after = max(0, int(LOGIN_PROTECTION_SECONDS - age.total_seconds()))
            return JsonResponse(
                {
                    "error": "Login protection active",
                    "reason": "login_protection",
                    "retry_after": retry_after,
                },
                status=409,
            )

    login(request, user)
    return JsonResponse({"user": {"id": user.id, "username": user.username, "email": user.email}})



@ensure_csrf_cookie
def csrf_token_view(request):
    """显式下发 csrftoken cookie。

    供前端 SPA 启动时请求一次。开发态 webpack 直接服务模板、不经 Django 渲染，
    无法靠 {% csrf_token %} 下发 cookie；此端点把 cookie 下发与 HTML 渲染解耦，
    避免全新访客的匿名 POST（登录、找回密码等）被 403。
    """
    return JsonResponse({"detail": "CSRF cookie set"})


@require_POST
@login_required
def logout_view(request):
    user = request.user
    auth_logout(request)
    UserSession.objects.filter(user=user, is_current=True).update(is_current=False)
    return JsonResponse({"message": "Logged out"})


@login_required
def me_view(request):
    profile = _get_or_create_profile(request.user)
    return JsonResponse(_profile_response(request.user, profile))


@require_POST
def password_reset_view(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = PasswordResetForm(body)
    if not form.is_valid():
        return JsonResponse({"error": _form_errors(form)}, status=400)

    email = form.cleaned_data["email"]
    for user in User.objects.filter(email=email):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        send_mail(
            subject="Password Reset",
            message=f"{settings.FRONTEND_URL}/#/reset-password?uid={uid}&token={token}",
            from_email="webmaster@localhost",
            recipient_list=[email],
        )

    return JsonResponse({"message": "If an account with that email exists, a reset link has been sent."})


@require_POST
def password_reset_confirm_view(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = PasswordResetConfirmForm(body)
    if not form.is_valid():
        return JsonResponse({"error": _form_errors(form)}, status=400)

    try:
        user_id = force_str(urlsafe_base64_decode(form.cleaned_data["uid"]))
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"error": "Invalid reset link"}, status=400)

    if not default_token_generator.check_token(user, form.cleaned_data["token"]):
        return JsonResponse({"error": "Invalid or expired token"}, status=400)

    user.set_password(form.cleaned_data["new_password"])
    user.save()
    return JsonResponse({"message": "Password has been reset successfully."})


def _get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _capabilities(user):
    """前端能力契约：由 has_perm 派生的语义化布尔（解耦权限代号）。"""
    return {
        "can_manage_news": user.has_perm("news.add_news"),
        "can_manage_tasks": user.has_perm("tasks.manage_tasks"),
        "can_assign_task": user.has_perm("tasks.assign_task"),
        "can_manage_tags": user.has_perm("tasks.manage_tags"),
        "can_approve_proposals": user.has_perm("proposals.approve_proposal"),
        "can_change_proposals": user.has_perm("proposals.change_proposal"),
        "can_view_feedback": user.has_perm("proposals.view_feedback"),
    }


def _profile_response(user, profile):
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "permissions": _capabilities(user),
        },
        "profile": {
            "avatar": profile.avatar.url if profile.avatar else None,
            "nickname": profile.nickname,
            "birthday": profile.birthday.isoformat() if profile.birthday else None,
            "gender": profile.gender,
            "bio": profile.bio,
        },
    }


@login_required
def profile_view(request):
    profile = _get_or_create_profile(request.user)
    return JsonResponse(_profile_response(request.user, profile))


@require_POST
@login_required
def profile_update_view(request):
    profile = _get_or_create_profile(request.user)

    avatar = request.FILES.get("avatar")
    if avatar:
        if avatar.size > 2 * 1024 * 1024:
            return JsonResponse({"error": "头像文件不能超过 2MB"}, status=400)
        if avatar.content_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            return JsonResponse({"error": "仅支持 JPG、PNG、GIF、WebP 格式"}, status=400)
        profile.avatar = avatar

    form = ProfileForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"error": _form_errors(form)}, status=400)

    for field in ("nickname", "birthday", "gender", "bio"):
        setattr(profile, field, form.cleaned_data[field])

    profile.save()
    return JsonResponse(_profile_response(request.user, profile))


@require_POST
@login_required
def change_password_view(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    form = ChangePasswordForm(body)
    if not form.is_valid():
        return JsonResponse({"error": _form_errors(form)}, status=400)

    if not request.user.check_password(form.cleaned_data["old_password"]):
        return JsonResponse({"error": "原密码不正确"}, status=400)

    request.user.set_password(form.cleaned_data["new_password"])
    request.user.save()
    return JsonResponse({"message": "密码修改成功"})


@login_required
def users_view(request):
    """用户列表（给任务表单选人用）"""
    users = User.objects.select_related("profile").filter(is_active=True)
    data = []
    for u in users:
        profile = getattr(u, "profile", None)
        data.append({
            "id": u.id,
            "username": u.username,
            "nickname": profile.nickname if profile else "",
            "avatar": profile.avatar.url if profile and profile.avatar else None,
        })
    return JsonResponse({"results": data})
