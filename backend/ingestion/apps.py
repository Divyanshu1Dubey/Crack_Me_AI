"""AppConfig for the ingestion app."""
from django.apps import AppConfig


class IngestionConfig(AppConfig):
    name = "ingestion"
    verbose_name = "Production Content Ingestion Platform"
    default_auto_field = "django.db.models.BigAutoField"
