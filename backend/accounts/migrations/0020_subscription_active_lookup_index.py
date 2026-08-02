"""Covering index for ``Subscription.has_active_sub`` hot-path query.

The query is::

    Subscription.objects.filter(user=..., status='active').filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    ).exists()

A composite index on (user, status, expires_at) lets Postgres / SQLite
satisfy this with an index-only lookup. Without it the read path for
``is_premium()`` does a full scan of the user's subscription history.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_tokenconfig_ai_tutor_daily_cap"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(
                fields=["user", "status", "expires_at"],
                name="subscription_user_status_idx",
            ),
        ),
    ]