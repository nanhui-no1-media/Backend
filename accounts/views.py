import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.models import User


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
