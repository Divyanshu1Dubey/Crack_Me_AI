"""Django-native sign-in: email verification state, external identities, sessions, pending sign-ups.

Schema only (no data is changed): every existing account keeps its row, its
primary key and every relation to it. ``email_verified_at`` starts empty; it
is filled by ``manage.py import_supabase_auth`` (from Supabase's
``email_confirmed_at``), by an emailed verification link, by a completed
password reset and by a Google sign-up. Nothing reads the new tables while
AUTH_PROVIDER=supabase (the default). AdminAuditLog gains the actions of the
medical-accuracy mission (docs/audit/MEDICAL_ACCURACY_DESIGN.md section 3).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0027_rename_email_derived_usernames"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="email_verified_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="When the email address was verified (native sign-in requires it).",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="adminauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("token_grant", "Token Grant"),
                    ("token_revoke", "Token Revoke"),
                    ("token_transfer", "Token Transfer"),
                    ("token_view", "Token View"),
                    ("user_view", "User View"),
                    ("user_block", "User Block/Unblock"),
                    ("user_role_update", "User Role Update"),
                    ("user_progress_reset", "User Progress Reset"),
                    ("subscription_grant", "Subscription Grant"),
                    ("subscription_revoke", "Subscription Revoke"),
                    ("device_logout", "Device Force Logout"),
                    ("system_attempt_reset", "System Attempt Reset"),
                    ("system_analytics_clear", "System Analytics Clear"),
                    ("system_rerun_evaluation", "System Rerun Evaluation"),
                    ("identity_import", "Identity Import"),
                    ("identity_link", "Identity Link"),
                    ("recovery_link", "Recovery Link"),
                    ("email_change", "Email Change"),
                    ("session_revoke", "Session Revoke"),
                    ("answer_key_change", "Answer Key Change"),
                    ("evidence_review", "Evidence Review"),
                    ("audit_resolution", "Audit Resolution"),
                ],
                max_length=40,
            ),
        ),
        migrations.CreateModel(
            name="PendingSignup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(help_text="Lower-cased.", max_length=254, unique=True)),
                ("password", models.CharField(help_text="make_password() hash.", max_length=128)),
                ("username", models.CharField(blank=True, default="", max_length=150)),
                ("first_name", models.CharField(blank=True, default="", max_length=150)),
                ("last_name", models.CharField(blank=True, default="", max_length=150)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="AuthSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sid", models.CharField(max_length=64, unique=True)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("password", "Email and password"),
                            ("google", "Google"),
                            ("google_link", "Google (emailed link confirmation)"),
                            ("reset", "Password reset"),
                            ("verify", "Email verification"),
                            ("local", "Local development"),
                        ],
                        max_length=20,
                    ),
                ),
                ("refresh_jti", models.CharField(blank=True, default="", max_length=64)),
                ("previous_refresh_jti", models.CharField(blank=True, default="", max_length=64)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "expires_at",
                    models.DateTimeField(help_text="Absolute end of the session (NATIVE_AUTH_SESSION_MAX_DAYS)."),
                ),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "revoked_reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("logout", "Logout"),
                            ("password_reset", "Password reset"),
                            ("password_change", "Password change"),
                            ("refresh_reuse", "Refresh token reuse"),
                            ("device_logout", "Device logged out"),
                            ("blocked", "Account blocked"),
                            ("admin", "Revoked by an admin"),
                        ],
                        default="",
                        max_length=20,
                    ),
                ),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=255)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["user", "revoked_at"], name="authsession_user_revoked_idx")],
            },
        ),
        migrations.CreateModel(
            name="UserIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("google", "Google")], max_length=20)),
                ("subject", models.CharField(help_text="The provider's account id (Google: sub).", max_length=255)),
                (
                    "email",
                    models.EmailField(
                        blank=True, default="", help_text="Informational only; never matched.", max_length=254,
                    ),
                ),
                ("email_verified", models.BooleanField(default=False)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("supabase_import", "Imported from Supabase Auth"),
                            ("signup", "Signed up with this identity"),
                            ("email_confirmed", "Linked through an emailed confirmation link"),
                            ("user_linked", "Linked by the signed-in user"),
                            ("operator", "Linked by an operator"),
                        ],
                        max_length=20,
                    ),
                ),
                ("supabase_identity_id", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_sign_in_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["user", "provider"], name="useridentity_user_provider_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("provider", "subject"), name="useridentity_provider_subject_uniq"),
                ],
            },
        ),
    ]
