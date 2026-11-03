"""
Django management command to clean up Supabase admins.
Keeps only the 'deeksha' admin and deletes the OTHER ADMIN accounts.

Only accounts with admin rights in Supabase app_metadata (role "admin" or
is_admin true; writable by the service role only, the same rule as
sync_single_supabase_admin) are candidates. Students and every other
non-admin account are never deleted. Without --confirm it is a dry run.
"""
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

try:
    from supabase import create_client
    from supabase.lib.client_options import ClientOptions
except ImportError:
    raise CommandError(
        "Supabase client not installed. "
        "Install it with: pip install supabase"
    )

User = get_user_model()

KEEP_USERNAME = 'deeksha'
KEEP_EMAIL = 'meduraa.web@gmail.com'
PAGE_SIZE = 200
MAX_PAGES = 500


def _field(user, name):
    if isinstance(user, dict):
        return user.get(name)
    return getattr(user, name, None)


def is_supabase_admin(user) -> bool:
    """True only when app_metadata grants admin (never user_metadata)."""
    app_metadata = _field(user, 'app_metadata') or {}
    return (
        str(app_metadata.get('is_admin', '')).strip().lower() == 'true'
        or str(app_metadata.get('role', '')).strip().lower() == 'admin'
    )


def list_all_users(supabase):
    """Every Supabase Auth user, page by page (list_users is paginated)."""
    users = []
    for page in range(1, MAX_PAGES + 1):
        resp = supabase.auth.admin.list_users(page=page, per_page=PAGE_SIZE)
        batch = list((resp.users if hasattr(resp, 'users') else resp) or [])
        users.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return users


class Command(BaseCommand):
    help = (
        "Clean up Supabase admins: keep only 'deeksha', delete the other admin "
        "accounts (non-admin users are never deleted)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompting',
        )
        parser.add_argument(
            '--service-role-key',
            type=str,
            help='Supabase service role key (prefer the SUPABASE_SERVICE_ROLE_KEY env var)',
        )

    def handle(self, *args, **options):
        # Get credentials
        supabase_url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
        service_role_key = options.get('service_role_key') or os.getenv('SUPABASE_SERVICE_ROLE_KEY')

        if not supabase_url:
            raise CommandError("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL not set")
        if not service_role_key:
            raise CommandError("SUPABASE_SERVICE_ROLE_KEY not set (export it as an environment variable).")

        self.stdout.write(f"Connecting to Supabase: {supabase_url}")

        # Initialize Supabase client with service role
        options_obj = ClientOptions(auto_refresh_token=False, persist_session=False)
        supabase = create_client(supabase_url, service_role_key, options=options_obj)

        try:
            # List all auth users
            self.stdout.write("Fetching all auth users...")
            users = list_all_users(supabase)

            if not users:
                self.stdout.write(self.style.SUCCESS("No users found in Supabase auth."))
                return

            admins = [user for user in users if is_supabase_admin(user)]
            self.stdout.write(
                f"Found {len(users)} total users, {len(admins)} with admin rights "
                f"({len(users) - len(admins)} non-admin users are left untouched)"
            )

            # Identify target and users to delete (admins only)
            target_user = None
            users_to_delete = []

            for user in admins:
                user_metadata = _field(user, 'user_metadata') or {}
                email = _field(user, 'email') or user_metadata.get('email', '') or ''
                display_name = user_metadata.get('full_name') or '-'
                uid = _field(user, 'id')

                self.stdout.write(f"  - {display_name} ({email}) [UID: {uid}]")

                if display_name.lower() == KEEP_USERNAME or email.lower() == KEEP_EMAIL:
                    target_user = (uid, email, display_name)
                else:
                    users_to_delete.append((uid, email, display_name))

            if not options['confirm']:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n{len(users_to_delete)} admin users will be DELETED. "
                        "Run with --confirm to proceed.\n"
                    )
                )
                return

            # Delete extra admins
            if users_to_delete:
                self.stdout.write(
                    self.style.WARNING(f"\nDeleting {len(users_to_delete)} admin users...")
                )
                for uid, email, name in users_to_delete:
                    try:
                        supabase.auth.admin.delete_user(uid)
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ Deleted: {name} ({email})")
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"  ✗ Failed to delete {name}: {str(e)}")
                        )

            # Ensure target admin exists or update it
            if target_user:
                uid, email, name = target_user
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nKeeping admin: {name} ({email})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nWarning: No existing '{KEEP_USERNAME}' admin found. Create it with "
                        "`python manage.py sync_single_supabase_admin` (it requires an "
                        "explicit password; none is stored in the code)."
                    )
                )

            self.stdout.write(
                self.style.SUCCESS("\n✓ Cleanup complete!")
            )

        except Exception as e:
            raise CommandError(f"Supabase operation failed: {str(e)}")
