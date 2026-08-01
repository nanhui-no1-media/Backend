import json
import logging
import mimetypes
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail

from .forms import LoginForm, PasswordResetForm, PasswordResetConfirmForm, ProfileForm, ChangePasswordForm
from .models import Profile, IdentityProof, UserSession
from .tokens import email_verification_token
from .throttles import RegisterThrottle, ResendVerificationThrottle
from .turnstile import verify_turnstile
from .utils import SESSION_HISTORY_LIMIT, get_client_ip
from .visibility import content_visibility, profile_view_for

logger = logging.getLogger(__name__)

LOGIN_PROTECTION_SECONDS = 600  # 登录保护窗口：登录后 10 分钟内他方新会话登录被拒
CONTENT_LIMIT = 15  # 个人中心每个内容 tab 返回的最近条数

# 自助注册（#28）证明材料约束
PROOF_MIN_COUNT = 1
PROOF_MAX_COUNT = 3
PROOF_MAX_BYTES = 5 * 1024 * 1024  # 单张 ≤ 5MB
PROOF_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
IDENTITY_CHOICE_KEYS = {key for key, _label in Profile.IDENTITY_CHOICES}


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


def _send_verification_email(user):
    """发邮箱验证邮件（链接 = FRONTEND_URL + #/verify-email?uid=&token=）。

    令牌绑定 user.email + email_verified（见 accounts.tokens）。发信失败仅记日志、不抛——
    账号已建，用户可走「重发验证邮件」（#29）补发，不因 SMTP 抖动回滚注册。
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/#/verify-email?uid={uid}&token={token}"
    try:
        send_mail(
            subject="邮箱验证 - 南汇一中传媒社",
            message=(
                "你好！请点击下方链接完成邮箱验证（注册后首次登录需要）：\n\n"
                f"{link}\n\n"
                "如果你没有注册过本社团账号，请忽略此邮件。"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("发送邮箱验证邮件失败: user_pk=%s", user.pk)


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

    # 用 check_password 而非 authenticate：密码正确后再区分「停用 / 未验证」，
    # 错误密码统一回 401，不泄露账号存在性与状态（防枚举）。
    candidate = User.objects.filter(username=username).first()
    if candidate is None or not candidate.check_password(form.cleaned_data["password"]):
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    # 密码正确 → 确为本人，可安全揭示账号状态（自助注册三态：未验证 / 已停用 / 放行）。
    if not candidate.is_active:
        return JsonResponse(
            {"error": "账号已停用，请联系信息组。", "reason": "account_disabled"},
            status=403,
        )
    if not _email_verified(candidate):
        return JsonResponse(
            {
                "error": "请先验证邮箱后再登录。",
                "reason": "email_not_verified",
                "email": candidate.email,
            },
            status=403,
        )

    # 10 分钟登录保护：该账号已有当前会话且登录未满窗口、且非同一会话再认证 → 拒绝
    existing = UserSession.objects.filter(user=candidate, is_current=True).first()
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

    login(request, candidate)
    return JsonResponse({"user": {"id": candidate.id, "username": candidate.username, "email": candidate.email}}) # type: ignore



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


@require_GET
@login_required
def sessions_view(request):
    """本人最近登录记录（设备/IP/时间，当前会话高亮），按时间倒序裁剪到历史上限。"""
    rows = (
        UserSession.objects.filter(user=request.user)
        .order_by("-created_at", "-id")[:SESSION_HISTORY_LIMIT]
    )
    return JsonResponse({
        "results": [
            {
                "id": r.id, # type: ignore
                "device_name": r.device_name,
                "device_type": r.device_type,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat(),
                "is_current": r.is_current,
            }
            for r in rows
        ]
    })


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


@require_POST
def register_view(request):
    """自助注册（#28）：访客提交 → 建号（未验证）→ 发验证邮件。

    multipart：username / password+password2 / real_name / identity / email /
    turnstile_token / proof_files[]（1~3 张，jpg/png/webp，单张 ≤5MB）。一个事务建
    User(is_active=True) + Profile（显式未验证）+ IdentityProof。发信失败不回滚。
    限流 register scope（每 IP 5/日），Turnstile 在 DEBUG/未配 secret 时跳过。
    """
    # 限流优先：挡机器刷号（在所有校验之前）。
    if not RegisterThrottle().allow_request(request, None):
        return JsonResponse({"error": "注册请求过于频繁，请稍后再试。"}, status=429)

    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""
    password2 = request.POST.get("password2") or ""
    real_name = (request.POST.get("real_name") or "").strip()
    identity = (request.POST.get("identity") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()  # 邮箱全局大小写不敏感：归一化小写存储
    turnstile_token = request.POST.get("turnstile_token") or ""
    proof_files = request.FILES.getlist("proof_files")

    errors = []

    if not username:
        errors.append("用户名不能为空")
    if not email:
        errors.append("邮箱不能为空")
    if not real_name:
        errors.append("真实姓名不能为空")
    if identity not in IDENTITY_CHOICE_KEYS:
        errors.append("请选择有效身份（在校生 / 外校生 / 毕业生）")

    if password != password2:
        errors.append("两次输入的密码不一致")
    if password:
        try:
            validate_password(password)
        except ValidationError as e:
            errors.extend(e.messages)

    # 唯一性：用户名、邮箱均大小写不敏感
    if username and User.objects.filter(username__iexact=username).exists():
        errors.append("该用户名已被占用")
    if email and User.objects.filter(email__iexact=email).exists():
        errors.append("该邮箱已注册")

    # 证明材料：数量 / 类型 / 大小
    if len(proof_files) < PROOF_MIN_COUNT:
        errors.append(f"请至少上传 {PROOF_MIN_COUNT} 张身份证明照片")
    elif len(proof_files) > PROOF_MAX_COUNT:
        errors.append(f"身份证明最多 {PROOF_MAX_COUNT} 张")
    for f in proof_files:
        if f.size > PROOF_MAX_BYTES:
            errors.append(f"证明材料「{f.name}」超过 5MB 上限")
        if f.content_type not in PROOF_ALLOWED_TYPES:
            errors.append(f"证明材料「{f.name}」格式不支持（仅 JPG / PNG / WebP）")

    if errors:
        return JsonResponse({"error": errors[0] if len(errors) == 1 else errors}, status=400)

    # Turnstile 人机校验（DEBUG / 未配 secret 时 verify_turnstile 直接放行）
    if not verify_turnstile(turnstile_token, get_client_ip(request)):
        return JsonResponse({"error": "人机校验失败，请刷新后重试。"}, status=400)

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, email=email, password=password, is_active=True
            )
            # 自助注册：显式置未验证（profile 默认 True 是信任态，此处覆盖为待验证）。
            Profile.objects.create(
                user=user,
                real_name=real_name,
                identity=identity,
                email_verified=False,
                identity_verified=False,
            )
            for f in proof_files:
                IdentityProof.objects.create(user=user, file=f)
    except Exception:
        logger.exception("注册建号失败: username=%s", username)
        return JsonResponse({"error": "注册失败，请稍后重试。"}, status=500)

    # 发验证邮件（失败不回滚；用户可走「重发」补发）。
    _send_verification_email(user)

    return JsonResponse(
        {"message": "注册成功，请查收邮件完成邮箱验证。", "user": {"id": user.id, "username": user.username}},
        status=201,
    )


@require_GET
def verify_email_view(request):
    """邮箱验证（#29）：GET /auth/verify-email/?uid=&token= → 校验通过则置 email_verified=True。

    令牌绑定 user.email + email_verified（见 tokens），故改邮箱或已验证后旧令牌失效。
    """
    user = _user_from_uid(request.GET.get("uid", ""))
    token = request.GET.get("token", "")
    if user is None or not email_verification_token.check_token(user, token):
        return JsonResponse({"error": "验证链接无效或已过期。", "reason": "invalid"}, status=400)

    profile = _get_or_create_profile(user)
    if not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
    return JsonResponse({"message": "邮箱验证成功，现在可以登录了。"})


@require_POST
def resend_verification_view(request):
    """重发验证邮件（#29）：POST {email}，resend_verification scope 限流。

    不泄密：无论邮箱是否存在 / 是否已验证，返回同样提示（防账号探测）。
    只对「存在、启用、未验证」的账号真正发信。
    """
    if not ResendVerificationThrottle().allow_request(request, None):
        return JsonResponse({"error": "请求过于频繁，请稍后再试。"}, status=429)

    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = (body.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"error": "请输入邮箱。"}, status=400)

    user = User.objects.filter(email__iexact=email).first()
    if user is not None and user.is_active and not _email_verified(user):
        _send_verification_email(user)

    return JsonResponse({"message": "如果该邮箱已注册且尚未验证，验证邮件已重发。"})


@login_required
def identity_proof_file_view(request, pk):
    """身份证明鉴权下载（#31）：仅本人或持 can_review_identity 者可读。

    文件存 PRIVATE_MEDIA_ROOT 私有存储，绝不经公开 MEDIA_URL 暴露（DEBUG 下亦然——
    config/urls.py 的 static(MEDIA_URL) 只服务 MEDIA_ROOT，私有存储在其外）。
    """
    proof = get_object_or_404(IdentityProof, pk=pk)
    user = request.user
    if proof.user_id != user.pk and not user.has_perm("accounts.can_review_identity"):
        return HttpResponseForbidden("无权访问该身份证明。")

    if not proof.file.storage.exists(proof.file.name):
        raise Http404("证明文件不存在")

    content_type, _ = mimetypes.guess_type(proof.file.name)
    return FileResponse(
        proof.file.open("rb"),
        content_type=content_type or "image/jpeg",
    )


def _get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _email_verified(user):
    """登录门槛：profile.email_verified。无 profile 的存量 / admin 用户视为已验证（保持既有行为）。"""
    profile = getattr(user, "profile", None)
    return profile is None or profile.email_verified


def _user_from_uid(uid):
    """uid（urlsafe_base64）→ User；非法返回 None。"""
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        return User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None


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


ROLE_PRIORITY = ["社长", "信息组"]  # 前者优先；都不在则归 "member"


def _role_for(user):
    """主角色 {label, variant}：社长 > 信息组 > 成员。variant 供前端配色。"""
    user_groups = set(user.groups.values_list("name", flat=True))
    for name in ROLE_PRIORITY:
        if name in user_groups:
            return {"label": name, "variant": "president" if name == "社长" else "info"}
    return {"label": "成员", "variant": "member"}


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
            # 自助注册验证状态（#30）：前端据此显 Tier-2 待审核提示条
            "email_verified": profile.email_verified,
            "identity_verified": profile.identity_verified,
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
            "id": u.id, # type: ignore
            "username": u.username,
            "nickname": profile.nickname if profile else "",
            "avatar": profile.avatar.url if profile and profile.avatar else None,
        })
    return JsonResponse({"results": data})


@require_GET
@login_required
def user_profile_view(request, id):
    """查看任意用户的主页资料（按请求者身份裁剪字段，委托可见性模块）。"""
    viewed = User.objects.filter(pk=id, is_active=True).first()
    if viewed is None:
        return JsonResponse({"error": "用户不存在"}, status=404)

    profile = _get_or_create_profile(viewed)
    visibility = profile_view_for(request.user, viewed)

    data = {
        "user": {
            "id": viewed.id,
            "username": viewed.username,
            "date_joined": viewed.date_joined.isoformat(),
        },
        "profile": {
            "avatar": profile.avatar.url if profile.avatar else None,
            "nickname": profile.nickname,
            "bio": profile.bio,
        },
        "role": _role_for(viewed),
        "viewer": {"is_owner": visibility.is_owner, "is_admin": visibility.is_admin},
    }

    if visibility.can_see_private:
        data["user"]["email"] = viewed.email
        data["profile"]["birthday"] = profile.birthday.isoformat() if profile.birthday else None
        data["profile"]["gender"] = profile.gender

    if visibility.can_see_sensitive:
        data["permissions"] = _capabilities(viewed)
        data["groups"] = list(viewed.groups.values_list("name", flat=True))

    return JsonResponse(data)


@require_GET
@login_required
def user_content_view(request, id):
    """某用户的 tab 内容（按身份裁剪可见性，委托可见性模块）。"""
    viewed = User.objects.filter(pk=id, is_active=True).first()
    if viewed is None:
        return JsonResponse({"error": "用户不存在"}, status=404)

    type_ = request.GET.get("type")
    if type_ not in ("news", "proposals", "tasks"):
        return JsonResponse({"error": "无效的 type"}, status=400)

    visibility = content_visibility(request.user, viewed, type_)
    if visibility.denied:
        return JsonResponse({"error": "无权查看他人任务"}, status=403)

    if type_ == "news":
        from news.models import News
        qs = News.objects.filter(author=viewed, **visibility.extra_filter)
        results = [{
            "id": n.id,
            "title": n.title,
            "category": n.category,
            "cover_image": n.cover_image.url if n.cover_image else None,
            "is_published": n.is_published,
            "published_at": (n.published_at or n.created_at).isoformat(),
        } for n in qs[:CONTENT_LIMIT]]

    elif type_ == "proposals":
        from proposals.models import Proposal
        qs = Proposal.objects.filter(creator=viewed, **visibility.extra_filter)
        results = [{
            "id": p.id,
            "title": p.title,
            "proposal_type": p.proposal_type,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
        } for p in qs[:CONTENT_LIMIT]]

    else:  # tasks（visibility.denied 已保证仅本人到此）
        from tasks.models import Task
        qs = Task.objects.filter(assignee=viewed, **visibility.extra_filter)
        results = [{
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at.isoformat(),
        } for t in qs[:CONTENT_LIMIT]]

    return JsonResponse({"results": results})

