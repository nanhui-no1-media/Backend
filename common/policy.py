"""Runtime site policy snapshot.

Operational knobs live in the ``SiteSettings`` singleton. Callers import
``get_policy()`` only — never query the model. Secrets / infra stay in
``config/settings.py`` + ``.env`` (ADR-0010).
"""
from __future__ import annotations

from dataclasses import dataclass

from django.core.cache import cache
from django.db.utils import OperationalError, ProgrammingError

CACHE_KEY = "common.site_policy"

# Defaults equal today's previously hardcoded values (behavior-neutral deploy).
DEFAULT_VERIFICATION_ENABLED = True
DEFAULT_REGISTRATION_ENABLED = True
DEFAULT_REGISTER_PER_IP_PER_DAY = 5
DEFAULT_RESEND_VERIFICATION_PER_IP_PER_HOUR = 5
DEFAULT_FEEDBACK_ANON_PER_IP_PER_DAY = 10
DEFAULT_SYNC_UPLOAD_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_TUS_MEDIA_MAX_BYTES = 500 * 1024 * 1024


@dataclass(frozen=True)
class SitePolicy:
    verification_enabled: bool
    registration_enabled: bool
    register_per_ip_per_day: int
    resend_verification_per_ip_per_hour: int
    feedback_anon_per_ip_per_day: int
    sync_upload_max_bytes: int
    tus_media_max_bytes: int

    @classmethod
    def defaults(cls) -> SitePolicy:
        return cls(
            verification_enabled=DEFAULT_VERIFICATION_ENABLED,
            registration_enabled=DEFAULT_REGISTRATION_ENABLED,
            register_per_ip_per_day=DEFAULT_REGISTER_PER_IP_PER_DAY,
            resend_verification_per_ip_per_hour=DEFAULT_RESEND_VERIFICATION_PER_IP_PER_HOUR,
            feedback_anon_per_ip_per_day=DEFAULT_FEEDBACK_ANON_PER_IP_PER_DAY,
            sync_upload_max_bytes=DEFAULT_SYNC_UPLOAD_MAX_BYTES,
            tus_media_max_bytes=DEFAULT_TUS_MEDIA_MAX_BYTES,
        )


def format_byte_cap(n: int) -> str:
    """Human label for an upload cap (e.g. ``50MB``) used in error text."""
    if n >= 1024 * 1024 and n % (1024 * 1024) == 0:
        return f"{n // (1024 * 1024)}MB"
    if n >= 1024 and n % 1024 == 0:
        return f"{n // 1024}KB"
    return f"{n} 字节"


def _snapshot(row) -> SitePolicy:
    if row is None:
        return SitePolicy.defaults()
    return SitePolicy(
        verification_enabled=row.verification_enabled,
        registration_enabled=row.registration_enabled,
        register_per_ip_per_day=row.register_per_ip_per_day,
        resend_verification_per_ip_per_hour=row.resend_verification_per_ip_per_hour,
        feedback_anon_per_ip_per_day=row.feedback_anon_per_ip_per_day,
        sync_upload_max_bytes=row.sync_upload_max_bytes,
        tus_media_max_bytes=row.tus_media_max_bytes,
    )


def get_policy() -> SitePolicy:
    """Return the cached site-policy snapshot (defaults if no row yet)."""
    cached = cache.get(CACHE_KEY)
    if isinstance(cached, SitePolicy):
        return cached
    from .models import SiteSettings

    try:
        row = SiteSettings.objects.filter(pk=1).first()
    except (OperationalError, ProgrammingError):
        return SitePolicy.defaults()
    policy = _snapshot(row)
    cache.set(CACHE_KEY, policy, timeout=None)
    return policy


def invalidate_policy_cache() -> None:
    cache.delete(CACHE_KEY)
