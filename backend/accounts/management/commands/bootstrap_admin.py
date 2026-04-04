import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create/update a default admin user for production bootstrap"

    def handle(self, *args, **options):
        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip() or "admin"
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@cracklabs.app").strip() or "admin@cracklabs.app"
        password = (
            os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
            or os.getenv("DJANGO_SUPERUSER_PASSWORD", "").strip()
            or "Kali2712@"
        )

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})

        if not user.email:
            user.email = email

        user.is_active = True
        user.is_staff = True
        user.is_superuser = True

        # Keep frontend role checks consistent with Django admin permissions.
        if hasattr(user, "role"):
            user.role = "admin"

        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated admin user '{username}'"))
