from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import sync_appointment_channel
from .utils import record_user_session


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    # Django's login() may call flush() (not cycle_key()) when signing in over
    # an already-authenticated different-user session, leaving session_key=None
    # at signal time. Materialize a fresh key so we always record the session.
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    if session_key:
        record_user_session(request, user, session_key)


@receiver(post_save, sender=User)
def on_user_saved(sender, instance, raw=False, **kwargs):
    # 后台委任通道随 is_staff / is_superuser 同步（ADR-0013）。loaddata raw 跳过。
    if raw:
        return
    sync_appointment_channel(instance)
