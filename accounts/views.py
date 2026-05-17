import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login
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
