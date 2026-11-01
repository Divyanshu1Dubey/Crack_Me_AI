"""Create the initial Django admin superuser for a fresh deployment.

Safe to re-run: the account is created only when it does not exist yet, and
an existing account is never modified (no password reset, no privilege
change). There is deliberately no default password: the command refuses to
run unless BOOTSTRAP_ADMIN_PASSWORD (or DJANGO_SUPERUSER_PASSWORD) is set.

Environment:
    BOOTSTRAP_ADMIN_PASSWORD   required; alias DJANGO_SUPERUSER_PASSWORD
    BOOTSTRAP_ADMIN_USERNAME   default "admin"
    BOOTSTRAP_ADMIN_EMAIL      default "admin@cracklabs.app"

The shared default password and the student ("d1") bootstrap account were
removed; their environment variables are ignored.
"""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

REMOVED_ENV_VARS = (
    "BOOTSTRAP_DEFAULT_PASSWORD",
    "BOOTSTRAP_STUDENT_USERNAME",
    "BOOTSTRAP_STUDENT_EMAIL",
    "BOOTSTRAP_STUDENT_PASSWORD",
)


class Command(BaseCommand):
    help = (
        "Create the initial admin superuser if it does not exist yet. Requires "
        "BOOTSTRAP_ADMIN_PASSWORD; never resets an existing user's password."
    )

    def handle(self, *args, **options):
        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip() or "admin"
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip() or "admin@cracklabs.app"
        password = (
            os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
            or os.getenv("DJANGO_SUPERUSER_PASSWORD", "").strip()
        )

        ignored = [name for name in REMOVED_ENV_VARS if os.getenv(name)]
        if ignored:
            self.stderr.write(self.style.WARNING(
                f"Ignoring {', '.join(ignored)}: the shared default password and the "
                "student bootstrap account were removed."
            ))

        if not password:
            raise CommandError(
                "Refusing to bootstrap an admin without an explicit password: set "
                "BOOTSTRAP_ADMIN_PASSWORD (there is no default)."
            )

        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing is not None:
            note = "" if (existing.is_staff and existing.is_superuser) else (
                " It is not a staff superuser; promote it manually if that is intended."
            )
            self.stdout.write(self.style.WARNING(
                f"User '{username}' already exists; left unchanged (password not reset).{note}"
            ))
            return

        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                f"Another account already uses {email}; refusing to create a second "
                "admin for it. Set BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_EMAIL explicitly."
            )

        try:
            validate_password(password, user=User(username=username, email=email))
        except ValidationError as exc:
            raise CommandError(
                "BOOTSTRAP_ADMIN_PASSWORD was rejected by the password validators: "
                + " ".join(exc.messages)
            ) from None

        extra = {"role": "admin"} if hasattr(User, "role") else {}
        User.objects.create_superuser(username=username, email=email, password=password, **extra)
        self.stdout.write(self.style.SUCCESS(f"Created admin superuser '{username}'."))
