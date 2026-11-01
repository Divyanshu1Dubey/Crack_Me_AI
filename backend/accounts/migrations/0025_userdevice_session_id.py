"""Bind each device to the Supabase auth session that uses it.

The device cap used to count only the client-sent X-Session-ID header: a
request without it was not counted at all, and a logged-out device kept its
access by omitting the header. ``session_id`` (the access token's
``session_id`` claim) is the binding the client cannot omit or forge; see
accounts.supabase_rest_auth.SupabaseJWTAuthentication._enforce_device_limits.
Existing rows start empty and are bound on their session's next request.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_customuser_scholarship_challenge"),
    ]

    operations = [
        migrations.AddField(
            model_name="userdevice",
            name="session_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default=None,
                help_text="Supabase auth session (access-token session_id claim) bound to this device.",
                max_length=64,
                null=True,
            ),
        ),
    ]
