import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail


@csrf_exempt
@require_POST
def login_view(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    username = body.get("username")
    email = body.get("email")
    password = body.get("password", "")

    if not password:
        return JsonResponse({"error": "Password is required"}, status=400)

    if not username and not email:
        return JsonResponse({"error": "Username or email is required"}, status=400)

    if email and not username:
        try:
            username = User.objects.get(email=email).username
        except User.DoesNotExist:
            return JsonResponse({"error": "Invalid credentials"}, status=401)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    login(request, user)
    return JsonResponse({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    })


@csrf_exempt
@require_POST
def register_view(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    username = body.get("username", "")
    email = body.get("email", "")
    password = body.get("password", "")

    if not all([username, email, password]):
        return JsonResponse({"error": "Username, email, and password are required"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken"}, status=409)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=409)

    user = User.objects.create_user(username=username, email=email, password=password)
    return JsonResponse({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    }, status=201)


@csrf_exempt
@require_POST
def logout_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)
    auth_logout(request)
    return JsonResponse({"message": "Logged out"})


def me_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)
    return JsonResponse({
        "user": {
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
        }
    })


@csrf_exempt
@require_POST
def password_reset_view(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = body.get("email", "")
    if not email:
        return JsonResponse({"error": "Email is required"}, status=400)

    users = User.objects.filter(email=email)
    for user in users:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        send_mail(
            subject="Password Reset",
            message=f"http://localhost:3000/reset-password?uid={uid}&token={token}",
            from_email="webmaster@localhost",
            recipient_list=[email],
        )

    return JsonResponse({"message": "If an account with that email exists, a reset link has been sent."})


@csrf_exempt
@require_POST
def password_reset_confirm_view(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    uid = body.get("uid", "")
    token = body.get("token", "")
    new_password = body.get("new_password", "")

    if not all([uid, token, new_password]):
        return JsonResponse({"error": "uid, token, and new_password are required"}, status=400)

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"error": "Invalid reset link"}, status=400)

    if not default_token_generator.check_token(user, token):
        return JsonResponse({"error": "Invalid or expired token"}, status=400)

    user.set_password(new_password)
    user.save()
    return JsonResponse({"message": "Password has been reset successfully."})
