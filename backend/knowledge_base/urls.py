from django.urls import path

from . import views

urlpatterns = [
    path("ask/", views.AskMonicaView.as_view(), name="kb-ask"),
    path("search/", views.SearchView.as_view(), name="kb-search"),
    path("stats/", views.StatsView.as_view(), name="kb-stats"),
    path("sources/", views.SourcesView.as_view(), name="kb-sources"),
    path("upload/", views.UploadView.as_view(), name="kb-upload"),
    path("ingest/", views.IngestView.as_view(), name="kb-ingest"),
    path("index/", views.IndexEmbeddingsView.as_view(), name="kb-index"),
    path("extract-kg/", views.ExtractKGView.as_view(), name="kb-extract-kg"),
    path("eval/", views.EvalView.as_view(), name="kb-eval"),
    path("health/", views.HealthView.as_view(), name="kb-health"),
]