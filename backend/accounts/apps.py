from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Ensure the freemium models module is imported so makemigrations
        # and the ORM see FreeShowcaseQuestion.
        from . import models_freemium  # noqa: F401
        # Wire up post_migrate → freemium auto-seed (showcase + free preview tests).
        from . import signals  # noqa: F401