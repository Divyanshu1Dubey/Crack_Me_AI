"""URL routes for the INI-CET recall importer API.

Mounted at `/api/imports/inicet/` from `crack_cms/urls.py`. The jobs
endpoints list, show and retry INI-CET jobs only (see `views.py`).
"""
from django.urls import path

from . import views

app_name = "importers_inicet"

urlpatterns = [
    path("jobs/", views.ImportJobListView.as_view(), name="jobs-list"),
    path("jobs/<int:pk>/", views.ImportJobDetailView.as_view(), name="jobs-detail"),
    path("jobs/<int:pk>/retry/", views.ImportJobRetryView.as_view(), name="jobs-retry"),
    path("reports/<str:run_id>/", views.ImportReportView.as_view(), name="reports"),
]
