"""URL routing for the Admin Import Center.

All routes are staff-gated and live under ``/api/admin/import/`` to keep
the namespace clear of the consumer-facing public API.
"""
from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views
from .api_views import ExtractedQuestionViewSet, ImportBatchViewSet, UploadCreateBatchView

router = DefaultRouter(trailing_slash=True)
router.register(r"batches", ImportBatchViewSet, basename="import-batches")
router.register(r"questions", ExtractedQuestionViewSet, basename="import-questions")

urlpatterns = [
    path("upload/", UploadCreateBatchView.as_view(), name="import-upload"),
    path("dashboard/", api_views.dashboard, name="import-dashboard"),
    path("search/", api_views.search, name="import-search"),
    path("health/", api_views.health, name="import-health"),
    path("lookups/", api_views.subjects_topics, name="import-lookups"),
]

urlpatterns += router.urls
