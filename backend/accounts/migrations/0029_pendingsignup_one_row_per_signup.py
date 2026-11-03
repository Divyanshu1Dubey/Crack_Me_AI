"""PendingSignup: one row per sign-up instead of one per address.

With a unique email, a second sign-up with the same address replaced the
first one's password and link, so whoever opened the newest mail created
the account with the second party's password. Now every sign-up keeps its
own row (accounts.native_auth.NativeRegisterView) and opening a link needs
the password of one of the address's sign-ups. Schema only: existing rows
are kept (at most one per address so far).
"""

from django.db import migrations, models


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
    ]
