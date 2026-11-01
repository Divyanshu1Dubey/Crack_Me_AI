"""crack_cms URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

from .diagnostics import ClientIpDiagnosticsView


# Phase 4 — production-only safety nets.  Never raises in dev/CI. In
# production a fatal misconfiguration raises ImproperlyConfigured here, as
# security.py documents. Only the import is guarded: the old `except
# Exception` around the call also swallowed the check's own
# ImproperlyConfigured and logged it as an import failure. Skipped under the
# test runner (settings.TESTING): a non-DEBUG local test run is "production"
# by IS_PRODUCTION_RUNTIME, but settings substitutes a test SECRET_KEY there.
try:
    from .security import security_posture_check
except ImportError:  # pragma: no cover - defensive
    security_posture_check = None
    import logging
    logging.getLogger(__name__).warning(
        "security_posture_check failed to import — production checks disabled.",
        exc_info=True,
    )

if security_posture_check is not None:
    security_posture_check(
        is_production=(
            getattr(settings, "IS_PRODUCTION_RUNTIME", False)
            and not getattr(settings, "TESTING", False)
        ),
        is_ci=getattr(settings, "IS_CI", False),
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
    if not settings.DEBUG:
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound()
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
    except Exception:
        # Public endpoint: never echo DB driver errors (host / user names).
        import logging
        logging.getLogger(__name__).exception("Readiness check failed")
        return JsonResponse(
            {"status": "not-ready", "error": "database unavailable"},
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
    # Admin-only: which address headers reach Django (NUM_PROXIES /
    # TRUSTED_CLIENT_IP_HEADER setup, see settings.py).
    path("api/health/client-ip/", ClientIpDiagnosticsView.as_view(), name="health-client-ip"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/questions/", include("questions.urls")),
    path("api/tests/", include("tests_engine.urls")),
    path("api/analytics/", include("analytics.urls")),
    path("api/ai/", include("ai_engine.urls")),
    path("api/knowledge/", include("knowledge_base.urls")),
    path("api/textbooks/", include("textbooks.urls")),
    path("api/resources/", include("resources.urls")),
    # (The empty api/video/ mount is gone: video_engine.urls exposes nothing;
    # video generation is the questions endpoint + video_engine.tasks.)
    path("api/jobs/", include("jobs.urls")),
    path("api/imports/neetpg/", include("importers.neetpg.urls")),
    # INI-CET recall importer: the same admin-only (IsControlTowerAdmin) views
    # as NEET PG, dispatching importers.inicet.tasks.run_recall_import.
    path("api/imports/inicet/", include("importers.inicet.urls")),
    # Production Content Ingestion Platform (Phase 1, additive).
    path("api/ingestion/", include("ingestion.urls")),
    # Admin Import Center (Phase 1) — staff-only ingestion UI backend.
    path("api/admin/import/", include("material_importer.urls")),
    path("api/blog/", include("blog_engine.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
