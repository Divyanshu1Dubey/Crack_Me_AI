"""Django AppConfig for the recall importer."""
from django.apps import AppConfig


class ImportersConfig(AppConfig):
    name = "importers"
    verbose_name = "Recall Importers"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Lazy imports to avoid Django startup-time import cost.
        # Phase 2 doesn't ship signals here — keeps the surface minimal.
        return None