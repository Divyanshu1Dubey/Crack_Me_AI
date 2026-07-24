"""URL routes for the ingestion app.

Mounted at ``/api/ingestion/`` from ``crack_cms/urls.py``.
The namespace is isolated from existing UPSC CMS routes
(``/api/imports/neetpg/`` continues to work unchanged).
"""
from django.urls import path

from . import views

app_name = "ingestion"

urlpatterns = [
    # Materials
    path("materials/", views.MaterialAssetListView.as_view(), name="materials-list"),
    path("materials/upload/", views.MaterialAssetUploadView.as_view(), name="materials-upload"),
    path("materials/<str:sha16>/", views.MaterialAssetDetailView.as_view(), name="materials-detail"),

    # Jobs
    path("jobs/", views.ImportJobListView.as_view(), name="jobs-list"),
    path("jobs/<int:job_id>/", views.ImportJobDetailView.as_view(), name="jobs-detail"),
    path("jobs/<int:job_id>/retry/", views.ImportJobRetryView.as_view(), name="jobs-retry"),
    path("jobs/<int:job_id>/cancel/", views.ImportJobCancelView.as_view(), name="jobs-cancel"),
    path("jobs/<int:job_id>/checkpoints/", views.ImportCheckpointListView.as_view(), name="jobs-checkpoints"),
    path("jobs/<int:job_id>/logs/", views.ImportLogListView.as_view(), name="jobs-logs"),
    path("jobs/<int:job_id>/stages/", views.ImportJobStageListView.as_view(), name="jobs-stages"),
    path("jobs/<int:job_id>/staged-questions/", views.StagedQuestionListView.as_view(), name="jobs-staged-questions"),

    # Batches
    path("batches/", views.BatchRunListView.as_view(), name="batches-list"),
    path("batches/<int:batch_id>/", views.BatchRunDetailView.as_view(), name="batches-detail"),
]
