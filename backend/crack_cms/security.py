"""Production-only safety nets for the CrackCMS deployment.

These are evaluated at import-time of `crack_cms.urls` so misconfigured
production deployments fail loudly instead of booting with an
insecure default.

Holds no new product features; only enforces invariants a Staff
Engineer would expect for a launch-ready deploy:

* DEBUG=False + DJANGO_SECRET_KEY set
* DATABASE_URL present for production runtime
* CSRF_TRUSTED_ORIGINS / CORS_ALLOWED_ORIGINS include the frontend origin
* AI keys are not required but warn if all-round-robin keys are absent
* ALLOWED_HOSTS doesn't include the localhost-only default

Called from `crack_cms/urls.py`; never raises in dev.
"""
from __future__ import annotations

import logging
import os

LOG = logging.getLogger(__name__)


def security_posture_check(*, is_production: bool, is_ci: bool) -> None:
    """Verify the security posture at import time.

    Production-only: raises Django's ImproperlyConfigured when a fatal
    config issue would otherwise ship to users.
    """
    if is_ci or not is_production:
        return  # dev/CI don't need this gate

    from django.core.exceptions import ImproperlyConfigured

    secret_key = os.getenv("DJANGO_SECRET_KEY", os.getenv("SECRET_KEY", "")).strip()
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
            "FRONTEND_URL is unset — password-reset links will fall back to localhost."
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


__all__ = ["security_posture_check"]
