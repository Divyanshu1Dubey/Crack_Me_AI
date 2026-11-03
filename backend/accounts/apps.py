from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Ensure the freemium models module is imported so makemigrations
        # and the ORM see FreeShowcaseQuestion.
        from . import models_freemium  # noqa: F401
        # Wire up post_migrate → freemium auto-seed (showcase) and the
        # renewal-reminder schedule.
        from . import signals  # noqa: F401
        # Deployment checks (manage.py check --deploy): Supabase email
        # confirmation, token verify key, core-data backup path.
        from . import checks  # noqa: F401
