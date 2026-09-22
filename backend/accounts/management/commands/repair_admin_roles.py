"""
Django management command to repair admin-role loss.

Scans all users whose email matches CONTROL_TOWER_ADMIN_EMAILS or
BOOTSTRAP_ADMIN_EMAIL but whose Django role is NOT 'admin', and
restores admin privileges.

Usage:
    python manage.py repair_admin_roles
    python manage.py repair_admin_roles --dry-run
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()


def _admin_email_allowlist() -> set[str]:
    raw = os.getenv("CONTROL_TOWER_ADMIN_EMAILS", "")
    configured = {
        item.strip().lower()
        for item in raw.split(",")
        if item and item.strip()
    }
    bootstrap_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    if bootstrap_email:
        configured.add(bootstrap_email)
    return configured


class Command(BaseCommand):
    help = "Repair admin-role loss: restore admin for emails in the allowlist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report only, do not modify',
        )

    def handle(self, *args, **options):
        allowlist = _admin_email_allowlist()
        if not allowlist:
            self.stdout.write(
                self.style.WARNING("CONTROL_TOWER_ADMIN_EMAILS is empty. Nothing to repair.")
            )
            return

        broken = []
        for user in User.objects.all():
            email_lower = (user.email or "").strip().lower()
            if email_lower in allowlist and user.role != 'admin':
                broken.append(user)

        if not broken:
            self.stdout.write(self.style.SUCCESS("All allowlisted users already have role='admin'. Nothing to repair."))
            return

        self.stdout.write(f"Found {len(broken)} admin accounts with role='student':")
        for u in broken:
            self.stdout.write(f"  - {u.email} (id={u.pk}, role={u.role}, is_superuser={u.is_superuser})")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes made."))
            return

        for u in broken:
            u.role = 'admin'
            u.is_superuser = True
            u.is_staff = True
            u.save(update_fields=['role', 'is_superuser', 'is_staff'])
            self.stdout.write(self.style.SUCCESS(f"  ✓ Fixed: {u.email}"))

        self.stdout.write(self.style.SUCCESS(f"\nRepaired {len(broken)} accounts."))
