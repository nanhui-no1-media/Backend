from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .utils import record_user_session


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    session_key = request.session.session_key
    if session_key:
        record_user_session(request, user, session_key)
