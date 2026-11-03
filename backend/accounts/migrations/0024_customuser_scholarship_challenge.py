"""Persist the scholarship question set per user and attempt.

The set used to live in the cache for an hour, so a student who never
submitted could re-roll a fresh set every hour (and on every start while the
cache was down). ``scholarship_challenge`` starts empty; the next start of an
attempt stores its set.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0023_customuser_supabase_uid"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="scholarship_challenge",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text="Question set issued for the current scholarship attempt (kept until it is submitted).",
                null=True,
            ),
        ),
    ]
