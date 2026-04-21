import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.supabase_auth import (
    delete_supabase_auth_user,
    list_supabase_auth_users,
    upsert_supabase_auth_user,
)


def _upsert_local_user(User, *, username, email, password, role, is_staff, is_superuser):
    user, _created = User.objects.get_or_create(username=username, defaults={"email": email})

    if not user.email:
        user.email = email

    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = is_superuser

    if hasattr(user, "role"):
        user.role = role

    user.set_password(password)
    user.save()
    return user


class Command(BaseCommand):
    help = "Create one Supabase admin user and delete the other Supabase admin accounts."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="deeksha", help="Admin username to keep")
        parser.add_argument("--email", default="meduraa.web@gmail.com", help="Admin email to keep")
        parser.add_argument("--password", default="Kali2712@", help="Admin password to set")
        parser.add_argument(
            "--soft-delete",
            action="store_true",
            help="Soft-delete extra admins instead of permanently deleting them.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip() or "deeksha"
        email = options["email"].strip() or "meduraa.web@gmail.com"
        password = options["password"]
        soft_delete = bool(options.get("soft_delete"))

        if not email or not password:
            raise CommandError("Both --email and --password are required.")

        User = get_user_model()
        _upsert_local_user(
            User,
            username=username,
            email=email,
            password=password,
            role="admin",
            is_staff=True,
            is_superuser=True,
        )

        if not os.getenv("SUPABASE_URL", "").strip() or not os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
            raise CommandError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to sync/delete Supabase Auth users."
            )

        upsert_ok = upsert_supabase_auth_user(
            email=email,
            password=password,
            username=username,
            user_metadata={
                "username": username,
                "first_name": username,
            },
            app_metadata={
                "role": "admin",
                "is_admin": True,
            },
        )
        if not upsert_ok:
            raise CommandError("Failed to create or update the target Supabase admin user.")

        users = list_supabase_auth_users()
        deleted_count = 0
        kept_count = 0

        for user in users:
            user_email = str(user.get("email") or "").strip().lower()
            app_metadata = user.get("app_metadata") or {}
            is_admin = str(app_metadata.get("is_admin", "")).strip().lower() == "true" or str(
                app_metadata.get("role", "")
            ).strip().lower() == "admin"
            if not is_admin:
                continue

            if user_email == email.lower():
                kept_count += 1
                continue

            if delete_supabase_auth_user(str(user.get("id") or ""), soft_delete=soft_delete):
                deleted_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Kept '{username}' <{email}> as the only Supabase admin candidate; deleted {deleted_count} other admin user(s)."
            )
        )
        if kept_count == 0:
            self.stdout.write(self.style.WARNING("Target admin was created/updated, but no matching admin was found in the existing Supabase list."))