from django.apps import AppConfig


class AiEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_engine'

    def ready(self):
        # Ensure the freemium usage models module is imported so
        # makemigrations and the ORM see AITutorDailyUsage.
        from . import models_usage  # noqa: F401