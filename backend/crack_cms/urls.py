"""crack_cms URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


# Phase 4 — production-only safety nets.  Never raises in dev/CI.
try:
    from .security import security_posture_check
    security_posture_check(
        is_production=getattr(settings, "IS_PRODUCTION_RUNTIME", False),
        is_ci=getattr(settings, "IS_CI", False),
    )
except Exception:  # pragma: no cover - defensive
    import logging
    logging.getLogger(__name__).warning(
        "security_posture_check failed to import — production checks disabled.",
        exc_info=True,
    )


def health_check(request):
    return JsonResponse({"status": "ok"})


def api_root(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "CrackCMS API",
            "endpoints": [
                "/api/auth/",
                "/api/questions/",
                "/api/tests/",
                "/api/ai/",
                "/api/analytics/",
            ],
        }
    )


def trigger_error(request):
    1 / 0


def health_live(request):
    """Liveness — process is running; no DB call so always fast."""
    return JsonResponse({"status": "live", "service": "crack_cms"})


def health_ready(request):
    """Readiness — DB must be reachable."""
    from django.db import connection
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
    except Exception as e:
        return JsonResponse(
            {"status": "not-ready", "error": str(e)},
            status=503,
        )
    return JsonResponse({"status": "ready", "service": "crack_cms"})


urlpatterns = [
    path("sentry-debug/", trigger_error),
    path("", health_check, name="health-check"),
    path("api/", api_root, name="api-root"),
    path("api/health/", health_check, name="health"),
    path("api/live/", health_live, name="health-live"),
    path("api/ready/", health_ready, name="health-ready"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/questions/", include("questions.urls")),
    path("api/tests/", include("tests_engine.urls")),
    path("api/analytics/", include("analytics.urls")),
    path("api/ai/", include("ai_engine.urls")),
    path("api/knowledge/", include("knowledge_base.urls")),
    path("api/textbooks/", include("textbooks.urls")),
    path("api/resources/", include("resources.urls")),
    path("api/video/", include("video_engine.urls")),
    path("api/jobs/", include("jobs.urls")),
    path("api/imports/neetpg/", include("importers.neetpg.urls")),
    # Production Content Ingestion Platform (Phase 1, additive).
    path("api/ingestion/", include("ingestion.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
