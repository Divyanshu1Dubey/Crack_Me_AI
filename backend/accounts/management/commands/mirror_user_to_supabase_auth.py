from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.supabase_auth import sync_user_to_supabase_auth


class Command(BaseCommand):
    help = "Mirror one existing Django user into Supabase Auth (auth.users)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Django username to mirror")
        parser.add_argument("--password", required=True, help="Password to set in Supabase Auth")

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User '{username}' not found") from exc

        if not user.email:
            raise CommandError("User has no email; Supabase Auth requires email")

        ok = sync_user_to_supabase_auth(
            email=user.email,
            password=password,
            username=user.username,
        )
        if not ok:
            raise CommandError(
                "Mirror failed. Ensure SUPABASE_AUTH_MIRROR_ENABLED=true and "
                "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY are set in backend environment."
            )

        self.stdout.write(self.style.SUCCESS(f"Mirrored '{username}' to Supabase Auth"))
