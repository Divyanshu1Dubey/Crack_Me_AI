"""PendingSignup: one row per sign-up instead of one per address.

With a unique email, a second sign-up with the same address replaced the
first one's password and link, so whoever opened the newest mail created
the account with the second party's password. Now every sign-up keeps its
own row (accounts.native_auth.NativeRegisterView) and opening a link needs
the password of one of the address's sign-ups. Schema only: existing rows
are kept (at most one per address so far).

Reversible: before the unique constraint comes back, the reverse keeps only
the newest sign-up of each address (pending sign-ups are short-lived; the
others would make the constraint fail).
"""

from django.db import migrations, models


def keep_newest_signup_per_address(apps, schema_editor):
    PendingSignup = apps.get_model("accounts", "PendingSignup")
    seen, extra = set(), []
    for pk, email in PendingSignup.objects.order_by("email", "-pk").values_list("pk", "email"):
        if email in seen:
            extra.append(pk)
        else:
            seen.add(email)
    if extra:
        PendingSignup.objects.filter(pk__in=extra).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0028_native_auth"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pendingsignup",
            name="email",
            field=models.EmailField(db_index=True, help_text="Lower-cased.", max_length=254),
        ),
        # Forward: nothing. Reverse (runs before the AlterField above is undone): drop duplicates.
        migrations.RunPython(migrations.RunPython.noop, keep_newest_signup_per_address),
    ]
