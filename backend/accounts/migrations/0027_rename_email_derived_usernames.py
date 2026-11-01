"""Give student accounts whose username shows their email a generated handle.

Usernames become writable in this release (PATCH /api/auth/profile/), and its
"This username is taken" answer tells the caller whether some account uses a
name. For usernames that are the email's local part -- the ones the
leaderboard hides (analytics.views._public_name) -- that would tell anyone
whether a given address uses CrackLabs. So the same release renames them
first: every student account whose username holds an '@' or is its email's
local part (any case, optional _<n> suffix, 140 / 130-char cut;
accounts.handles.exposes_email) gets a generated ``learner_<8 hex>`` handle,
exactly as ``manage.py rename_email_derived_usernames --apply`` does.

Safe for sign-in: Supabase sign-ins match supabase_uid, then the confirmed
email; tokens carry the user id; the dev-only local login also accepts the
email. Admin, staff and superuser accounts are left alone (they sign in to
Django admin by username); the command lists them by id. The renames cannot
be reverted (reverse is a no-op).
"""

from django.db import migrations


def rename_email_derived_usernames(apps, schema_editor):
    from accounts.handles import email_derived_accounts, rename_to_generated_handles

    User = apps.get_model("accounts", "CustomUser")
    students, _team = email_derived_accounts(User)
    rename_to_generated_handles(User, students)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_restore_paid_legacy_plans"),
    ]

    operations = [
        migrations.RunPython(rename_email_derived_usernames, migrations.RunPython.noop),
    ]
