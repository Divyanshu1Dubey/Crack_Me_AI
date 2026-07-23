"""URL routes for the recall importer API.

Mounted at `/api/imports/neetpg/` from `crack_cms/urls.py`.
"""
from django.urls import path

from . import views

app_name = "importers_neetpg"

urlpatterns = [
    path("jobs/", views.ImportJobListView.as_view(), name="jobs-list"),
    path("jobs/<int:pk>/", views.ImportJobDetailView.as_view(), name="jobs-detail"),
    path("jobs/<int:pk>/retry/", views.ImportJobRetryView.as_view(), name="jobs-retry"),
    path("reports/<str:run_id>/", views.ImportReportView.as_view(), name="reports"),
]