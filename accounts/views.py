import json
import logging
import mimetypes
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
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
from .models import Profile, IdentityProof, UserSession, Verification, is_verified
from .tokens import email_verification_token
from .throttles import RegisterThrottle, ResendVerificationThrottle
from .turnstile import verify_turnstile
from .utils import SESSION_HISTORY_LIMIT, get_client_ip
from .visibility import content_visibility, profile_view_for

logger = logging.getLogger(__name__)

LOGIN_PROTECTION_SECONDS = 600  # 登录保护窗口：登录后 10 分钟内他方新会话登录被拒
CONTENT_LIMIT = 15  # 个人中心每个内容 tab 返回的最近条数

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
    """发邮箱验证邮件到 **待验邮箱**（email 通道 identifier，非 User.email）。

    链接 = FRONTEND_URL + #/verify-email?uid=&token=。令牌绑 identifier + 通道 status
    （见 accounts.tokens）：改邮箱或验证通过后旧令牌失效。发信失败仅记日志、不抛——
    账号已建，用户可走「重发」补发，不因 SMTP 抖动回滚。无待验邮箱则不发。
    """
    v = user.verifications.filter(channel=Verification.CHANNEL_EMAIL).first()
    if v is None or not v.identifier:
        return  # 无待验邮箱：无可发（注册未留邮箱等情况）
    recipient = v.identifier
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/#/verify-email?uid={uid}&token={token}"
    try:
        send_mail(
            subject="邮箱验证 - 南汇一中传媒社",
            message=(
                "你好！请点击下方链接完成邮箱验证：\n\n"
                f"{link}\n\n"
                "如果你没有注册过本社团账号，请忽略此邮件。"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[recipient],
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

    # 密码正确 → 确为本人，可安全揭示账号状态（停用 / 放行）。
    if not candidate.is_active:
        return JsonResponse(
            {"error": "账号已停用，请联系信息组。", "reason": "account_disabled"},
            status=403,
        )
    # 登录与验证解耦（ADR-0006 决策 6）：未验证账号可登录为访客，仅 is_active 拒停用。
    # 写操作门禁由 IsVerified 单独管（未验证能登、能读，不能写）。

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


@require_GET
@login_required
def verification_status_view(request):
    """账号验证状态（#36）：总 is_verified + 各通道当前状态，数据驱动面板铺卡。

    每个已定义通道一卡，按 CHANNELS 序。无 Verification 行的通道 status="none"（前端映射
    「未绑定 / 未提交」）。通道对象键集与前端 VerificationPanel 契约（见契约测试）。
    """
    user = request.user
    rows = {v.channel: v for v in user.verifications.all()}
    channels = []
    for channel, _label in Verification.CHANNELS:
        v = rows.get(channel)
        channels.append({
            "channel": channel,
            "status": v.status if v else "none",
            "identifier": v.identifier if v else "",
            "verified_at": v.verified_at.isoformat() if v and v.verified_at else None,
        })
    return JsonResponse({"is_verified": is_verified(user), "channels": channels})


@require_POST
@login_required
def verification_email_bind_view(request):
    """邮箱通道绑定 / 重发 / 换邮（面板动作，#37 / ADR-0006）。

    统一为「email 通道置 pending + identifier=待验地址 + 发信」，``User.email`` 不动（待验邮箱
    不住此）——验证通过才晋升（见 verify_email_view）。故：
      - 首次绑定 / 重发同邮箱 → 建或刷新 pending 行并发信；
      - 换邮箱（含已验证旧邮箱）→ 回 pending(identifier=新)，旧 User.email 在新验证前仍有效；
      - 已验证同邮箱再绑 → no-op（不降级）。
    绑定时校验邮箱唯一（User.email 或他人 pending identifier）。
    """
    if not ResendVerificationThrottle().allow_request(request, None):
        return JsonResponse({"error": "请求过于频繁，请稍后再试。"}, status=429)

    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = (body.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"error": "请输入邮箱。"}, status=400)
    try:
        EmailValidator()(email)
    except ValidationError:
        return JsonResponse({"error": "邮箱格式不正确"}, status=400)

    user = request.user
    existing = user.verifications.filter(channel=Verification.CHANNEL_EMAIL).first()
    # 已验证同邮箱再绑 → no-op（不降级为 pending、不重发）
    if (
        existing is not None
        and existing.status == Verification.STATUS_APPROVED
        and existing.identifier == email
    ):
        return JsonResponse({"message": "该邮箱已验证。"})

    # 唯一性：不可绑他账号有效持有的邮箱（已验证 User.email 或他人 pending identifier）
    if _email_taken(email, exclude_user=user):
        return JsonResponse({"error": "该邮箱已被占用"}, status=400)

    if existing is None:
        Verification.objects.create(
            user=user, channel=Verification.CHANNEL_EMAIL,
            status=Verification.STATUS_PENDING, identifier=email,
        )
    else:
        # 换邮箱：回 pending + 新 identifier；旧 verified_at/by 随之失效（令牌绑 status 也失效）
        existing.status = Verification.STATUS_PENDING
        existing.identifier = email
        existing.verified_at = None
        existing.verified_by = None
        existing.save(update_fields=["status", "identifier", "verified_at", "verified_by"])

    _send_verification_email(user)
    return JsonResponse({"message": "验证邮件已发送，请查收。"})


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
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[email],
            fail_silently=True,
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
    """注册（ADR-0006）：建登录身份（用户名 + 密码 + Turnstile），邮箱可选。

    注册↔验证分离：不再强制邮箱 / 身份证明 / real_name / identity。新号无 Verification 行 ⇒
    未验证（访客）。若提供邮箱：建 email 通道 pending（identifier=待验地址）并发验证信，
    ``User.email`` 保持空（待验邮箱不住 User.email）——验证通过才晋升（见 verify_email_view）。
    real_name / identity 是可选资料（identity 若填须为合法枚举）。
    """
    # 限流优先：挡机器刷号（在所有校验之前）。
    if not RegisterThrottle().allow_request(request, None):
        return JsonResponse({"error": "注册请求过于频繁，请稍后再试。"}, status=429)

    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""
    password2 = request.POST.get("password2") or ""
    real_name = (request.POST.get("real_name") or "").strip()
    identity = (request.POST.get("identity") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()  # 邮箱大小写不敏感：归一化小写
    turnstile_token = request.POST.get("turnstile_token") or ""

    errors = []

    if not username:
        errors.append("用户名不能为空")
    if not password:
        errors.append("密码不能为空")
    if password != password2:
        errors.append("两次输入的密码不一致")
    if password:
        try:
            validate_password(password)
        except ValidationError as e:
            errors.extend(e.messages)

    # 身份是可选资料；填了须是合法枚举。
    if identity and identity not in IDENTITY_CHOICE_KEYS:
        errors.append("请选择有效身份（在校生 / 外校生 / 毕业生）")

    # 邮箱可选；填了须格式合法 + 唯一（User.email 或他人 pending identifier 均判重）。
    if email:
        try:
            EmailValidator()(email)
        except ValidationError:
            errors.append("邮箱格式不正确")
        if _email_taken(email):
            errors.append("该邮箱已被占用")

    # 用户名唯一（大小写不敏感）。
    if username and User.objects.filter(username__iexact=username).exists():
        errors.append("该用户名已被占用")

    if errors:
        return JsonResponse({"error": errors[0] if len(errors) == 1 else errors}, status=400)

    # Turnstile 人机校验（DEBUG / 未配 secret 时 verify_turnstile 直接放行）
    if not verify_turnstile(turnstile_token, get_client_ip(request)):
        return JsonResponse({"error": "人机校验失败，请刷新后重试。"}, status=400)

    try:
        with transaction.atomic():
            # User.email 只装已验证邮箱：注册阶段留空；邮箱验证通过才晋升写入。
            user = User.objects.create_user(
                username=username, email="", password=password, is_active=True
            )
            Profile.objects.create(user=user, real_name=real_name, identity=identity)
            if email:
                Verification.objects.create(
                    user=user, channel=Verification.CHANNEL_EMAIL,
                    status=Verification.STATUS_PENDING, identifier=email,
                )
    except Exception:
        logger.exception("注册建号失败: username=%s", username)
        return JsonResponse({"error": "注册失败，请稍后重试。"}, status=500)

    if email:
        _send_verification_email(user)

    return JsonResponse(
        {
            "message": "注册成功。" + ("请查收邮件完成邮箱验证。" if email else ""),
            "user": {"id": user.id, "username": user.username},
        },
        status=201,
    )


@require_GET
def verify_email_view(request):
    """邮箱验证：GET /auth/verify-email/?uid=&token= → email 通道 approved + 晋升 User.email。

    令牌绑 identifier + 通道 status（见 tokens）：改待验邮箱或验证通过后旧令牌失效。
    验证通过：identifier 晋升写入 User.email（绑定邮箱生效，可用邮箱登录 / 重置密码）。
    """
    user = _user_from_uid(request.GET.get("uid", ""))
    token = request.GET.get("token", "")
    if user is None or not email_verification_token.check_token(user, token):
        return JsonResponse({"error": "验证链接无效或已过期。", "reason": "invalid"}, status=400)

    v = user.verifications.filter(channel=Verification.CHANNEL_EMAIL).first()
    if v is None or not v.identifier:
        return JsonResponse({"error": "验证链接无效或已过期。", "reason": "invalid"}, status=400)

    # approved：identifier 晋升 → User.email（绑定邮箱生效）；令牌随 status 翻转失效，不可重放。
    if v.status != Verification.STATUS_APPROVED:
        v.status = Verification.STATUS_APPROVED
        v.verified_at = timezone.now()
        v.verified_by = None  # 邮箱自证，无审核人
        v.save(update_fields=["status", "verified_at", "verified_by"])
    if user.email != v.identifier:
        user.email = v.identifier
        user.save(update_fields=["email"])
    return JsonResponse({"message": "邮箱验证成功。"})


@require_POST
def resend_verification_view(request):
    """重发邮箱验证邮件：POST {email}，按 email 通道 identifier 查待验账号。

    不泄密：无论邮箱是否存在 / 是否在验 / 已验证，返回同样提示（防账号探测）。
    只对「存在 pending email 通道、账号启用」的账号真正发信（发往待验 identifier）。
    """
    if not ResendVerificationThrottle().allow_request(request, None):
        return JsonResponse({"error": "请求过于频繁，请稍后再试。"}, status=429)

    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = (body.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"error": "请输入邮箱。"}, status=400)

    v = (
        Verification.objects.select_related("user")
        .filter(
            channel=Verification.CHANNEL_EMAIL,
            status=Verification.STATUS_PENDING,
            identifier__iexact=email,
        )
        .first()
    )
    if v is not None and v.user.is_active:
        _send_verification_email(v.user)

    return JsonResponse({"message": "如果该邮箱正在验证中，验证邮件已重发。"})


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


def _email_taken(email, exclude_user=None):
    """邮箱是否已被他账号有效持有：User.email（已验证绑定）或他人 email 通道 identifier（含 pending）。

    绑定唯一性（ADR-0006 决策 10）：一个邮箱同一时刻只能被一个账号有效持有（已绑定或正在验）。
    """
    users = User.objects.filter(email__iexact=email)
    vs = Verification.objects.filter(channel=Verification.CHANNEL_EMAIL, identifier__iexact=email)
    if exclude_user is not None:
        users = users.exclude(pk=exclude_user.pk)
        vs = vs.exclude(user=exclude_user)
    return users.exists() or vs.exists()


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
        "can_edit_about": user.has_perm("about.change_aboutpage"),
    }


def _role_for(user):
    """身份徽章 {label, variant}：超管 > 管理员 > 用户 > 访客（ADR-0005 决策 7 / ADR-0006）。

    与组、权限解耦——纯身份态派生；variant 供前端徽章配色。「用户 / 访客」分界读
    ``is_verified``（任一验证通道通过即用户，否则访客）。
    """
    if not user.is_authenticated:
        return {"label": "访客", "variant": "visitor"}
    if user.is_superuser:
        return {"label": "超级管理员", "variant": "superadmin"}
    if user.is_staff:
        return {"label": "管理员", "variant": "admin"}
    if is_verified(user):
        return {"label": "用户", "variant": "user"}
    return {"label": "访客", "variant": "visitor"}


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
            # 验证态（ADR-0006）：前端据此显访客提示 / 引导去验证面板。
            "is_verified": is_verified(user),
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

