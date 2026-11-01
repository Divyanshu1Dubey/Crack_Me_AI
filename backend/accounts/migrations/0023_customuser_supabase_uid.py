"""Link Supabase identities by their user id; reword the unused session fields.

``supabase_uid`` starts empty for every existing row. The authenticator fills
it on the next sign-in (accounts.supabase_rest_auth); privileged rows are only
linked automatically for trusted admin identities, otherwise an operator runs
``manage.py link_supabase_identity``.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_tokentransaction_accounts_to_user_id_324ba9_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="supabase_uid",
            field=models.CharField(
                blank=True,
                default=None,
                help_text="Supabase Auth user id linked to this account (set on first sign-in).",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="customuser",
            name="session_key",
            field=models.CharField(
                blank=True,
                help_text="Unused legacy field. Sessions are not limited to one device; devices are tracked in UserDevice (2 free / 4 subscribed).",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="customuser",
            name="current_session_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Unused legacy field (see session_key); devices live in UserDevice.",
                max_length=255,
            ),
        ),
    ]
