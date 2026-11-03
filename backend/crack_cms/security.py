"""Production-only safety nets for the CrackCMS deployment.

These are evaluated at import-time of `crack_cms.urls` so misconfigured
production deployments fail loudly instead of booting with an
insecure default.

Holds no new product features; only enforces invariants a Staff
Engineer would expect for a launch-ready deploy:

* DEBUG=False + DJANGO_SECRET_KEY (or SECRET_KEY) set
* DATABASE_URL present for production runtime
* CSRF_TRUSTED_ORIGINS / CORS_ALLOWED_ORIGINS include the frontend origin
* AI keys are not required but warn if all-round-robin keys are absent
* ALLOWED_HOSTS doesn't include the localhost-only default
* warn when neither NUM_PROXIES nor TRUSTED_CLIENT_IP_HEADER is set (the
  rate limiters then see only the proxy's address), and when NUM_PROXIES
  alone is missing (DRF's throttles need it, and a Cloudflare header is only
  read when the hop it names is Cloudflare's)

Called from `crack_cms/urls.py` (not under the test runner); never raises
in dev.
"""
from __future__ import annotations

import logging
import os

from crack_cms.client_ip import num_proxies_from_env

LOG = logging.getLogger(__name__)


def configured_secret_key() -> str:
    """The secret key exactly as settings.py resolves it: DJANGO_SECRET_KEY,
    else SECRET_KEY. ``os.getenv("DJANGO_SECRET_KEY", fallback)`` returned
    ``""`` for a set-but-empty DJANGO_SECRET_KEY, so a deploy that settings
    accepted (SECRET_KEY set) failed this check on every request."""
    return (os.getenv("DJANGO_SECRET_KEY") or os.getenv("SECRET_KEY") or "").strip()


def security_posture_check(*, is_production: bool, is_ci: bool) -> None:
    """Verify the security posture at import time.

    Production-only: raises Django's ImproperlyConfigured when a fatal
    config issue would otherwise ship to users.
    """
    if is_ci or not is_production:
        return  # dev/CI don't need this gate

    from django.core.exceptions import ImproperlyConfigured

    secret_key = configured_secret_key()
    if secret_key in ("", "django-insecure-local-dev-only"):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a strong value in production."
        )

    if not os.getenv("DATABASE_URL", "").strip() and not os.getenv("SUPABASE_DATABASE_URL", "").strip():
        raise ImproperlyConfigured(
            "DATABASE_URL (or SUPABASE_DATABASE_URL) is required in production."
        )

    frontend = os.getenv("FRONTEND_URL", "").strip()
    if not frontend:
        LOG.warning(
            "FRONTEND_URL is unset — the default CORS/CSRF trusted origins, invite links and "
            "the robots.txt sitemap URL fall back to localhost."
        )

    cors = os.getenv("CORS_ALLOWED_ORIGINS", "")
    csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "")
    if frontend and frontend not in cors:
        LOG.warning("FRONTEND_URL=%r is not in CORS_ALLOWED_ORIGINS.", frontend)
    if frontend and frontend not in csrf:
        LOG.warning("FRONTEND_URL=%r is not in CSRF_TRUSTED_ORIGINS.", frontend)

    if "localhost" in os.getenv("ALLOWED_HOSTS", ""):
        LOG.warning(
            "ALLOWED_HOSTS contains localhost in production — strip it for prod."
        )

    # As settings.py resolves it: 1 on Railway when unset (its edge proxy).
    num_proxies_unset = num_proxies_from_env(os.environ) is None
    if num_proxies_unset and not os.getenv("TRUSTED_CLIENT_IP_HEADER", "").strip():
        LOG.warning(
            "Neither NUM_PROXIES nor TRUSTED_CLIENT_IP_HEADER is set: behind the platform proxy "
            "the question-bank limiter counts every anonymous visitor in the proxy's bucket and "
            "DRF's anon throttles key on the client-supplied X-Forwarded-For. See the client-IP "
            "notes in crack_cms/settings.py and backend/.env.example."
        )
    elif num_proxies_unset:
        # DRF's general throttles read NUM_PROXIES, and a Cloudflare header is
        # only read when the hop the platform proxy appended is Cloudflare's
        # (crack_cms/client_ip.py), which needs NUM_PROXIES as well.
        LOG.warning(
            "NUM_PROXIES is not set: DRF throttles key on the raw, client-controlled "
            "X-Forwarded-For, and a CF-Connecting-IP header is not read behind the platform proxy "
            "(sign-in limits and lockouts then share the proxy's address). Set NUM_PROXIES (Railway: 1)."
        )

    has_any_ai_key = any(
        bool(os.getenv(k, "").strip())
        for k in (
            "GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY",
            "OPENROUTER_API_KEY", "GITHUB_TOKEN", "COHERE_API_KEY",
            "MISTRAL_API_KEY", "DEEPSEEK_API_KEY",
        )
    )
    if not has_any_ai_key:
        LOG.warning(
            "No AI provider keys set — AI features will fall back to templates only."
        )


__all__ = ["configured_secret_key", "security_posture_check"]
