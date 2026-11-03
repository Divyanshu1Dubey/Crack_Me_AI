"""Give pre-Subscription purchases real Subscription rows; premium comes from rows only.

Accounts flagged ``is_subscribed`` before accounts.0011 have no Subscription
row and used to count as lifetime members -- including everyone who used the
unpaid POST /api/auth/subscribe/ endpoint (2026-07-02 to 2026-07-26). From
this release a flag without a row grants nothing, so this migration first
creates, for each flagged account without rows, the rows its signed Razorpay
payments prove: the ₹199 Early Bird pass as a lifetime 'legacy' row, a dated
plan with the period it bought (ended periods expire on the next read). See
accounts.legacy_subscriptions.

It only adds rows. Accounts with no payment evidence keep their (now inert)
flag until an owner reviews them:

    python manage.py reconcile_legacy_subscriptions                 # report
    python manage.py reconcile_legacy_subscriptions --apply --clear-unproven
"""

from django.db import migrations


def restore_paid_plans(apps, schema_editor):
    from accounts.legacy_subscriptions import reconcile

    reconcile(
        User=apps.get_model("accounts", "CustomUser"),
        Subscription=apps.get_model("accounts", "Subscription"),
        PaymentAttempt=apps.get_model("accounts", "PaymentAttempt"),
        TokenTransaction=apps.get_model("accounts", "TokenTransaction"),
        AuditLog=apps.get_model("accounts", "AdminAuditLog"),
        restore=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_userdevice_session_id"),
    ]

    operations = [
        migrations.RunPython(restore_paid_plans, migrations.RunPython.noop),
    ]
