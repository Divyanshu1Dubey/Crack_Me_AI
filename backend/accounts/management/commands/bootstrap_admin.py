import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


def _upsert_user(User, *, username, email, password, role, is_staff, is_superuser):
    user, created = User.objects.get_or_create(username=username, defaults={"email": email})

    if not user.email:
        user.email = email

    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = is_superuser

    if hasattr(user, "role"):
        user.role = role

    user.set_password(password)
    user.save()
    return created


class Command(BaseCommand):
    help = "Create/update default admin and student users for production bootstrap"

    def handle(self, *args, **options):
        default_password = os.getenv("BOOTSTRAP_DEFAULT_PASSWORD", "Kali2712@").strip() or "Kali2712@"

        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip() or "admin"
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@cracklabs.app").strip() or "admin@cracklabs.app"
        password = (
            os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
            or os.getenv("DJANGO_SUPERUSER_PASSWORD", "").strip()
            or default_password
        )

        student_username = os.getenv("BOOTSTRAP_STUDENT_USERNAME", "d1").strip() or "d1"
        student_email = os.getenv("BOOTSTRAP_STUDENT_EMAIL", "d1@cracklabs.app").strip() or "d1@cracklabs.app"
        student_password = os.getenv("BOOTSTRAP_STUDENT_PASSWORD", "").strip() or default_password

        User = get_user_model()

        admin_created = _upsert_user(
            User,
            username=username,
            email=email,
            password=password,
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        student_created = _upsert_user(
            User,
            username=student_username,
            email=student_email,
            password=student_password,
            role="student",
            is_staff=False,
            is_superuser=False,
        )

        if admin_created:
            self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated admin user '{username}'"))

        if student_created:
            self.stdout.write(self.style.SUCCESS(f"Created student user '{student_username}'"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated student user '{student_username}'"))
