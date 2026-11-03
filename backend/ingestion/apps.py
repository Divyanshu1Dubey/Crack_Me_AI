"""AppConfig for the ingestion app."""
from django.apps import AppConfig


class IngestionConfig(AppConfig):
    name = "ingestion"
    verbose_name = "Production Content Ingestion Platform"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # post_migrate → the stale-job sweeper's django-q Schedule.
        from . import signals  # noqa: F401
