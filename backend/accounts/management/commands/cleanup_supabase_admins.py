"""
Django management command to clean up Supabase admins.
Keeps only 'deeksha' admin and deletes all others.
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


class Command(BaseCommand):
    help = "Clean up Supabase admins: keep only 'deeksha', delete all others"

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompting',
        )
        parser.add_argument(
            '--service-role-key',
            type=str,
            help='Supabase service role key',
        )

    def handle(self, *args, **options):
        # Get credentials
        supabase_url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
        service_role_key = options.get('service_role_key') or os.getenv('SUPABASE_SERVICE_ROLE_KEY')

        if not supabase_url:
            raise CommandError("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL not set")
        if not service_role_key:
            raise CommandError(
                "SUPABASE_SERVICE_ROLE_KEY not set. "
                "Pass it with: --service-role-key YOUR_KEY"
            )

        self.stdout.write(f"Connecting to Supabase: {supabase_url}")
        
        # Initialize Supabase client with service role
        options_obj = ClientOptions(auto_refresh_token=False, persist_session=False)
        supabase = create_client(supabase_url, service_role_key, options=options_obj)

        try:
            # List all auth users
            self.stdout.write("Fetching all auth users...")
            resp = supabase.auth.admin.list_users()
            users = resp.users if hasattr(resp, 'users') else resp
            
            if not users:
                self.stdout.write(self.style.SUCCESS("No users found in Supabase auth."))
                return

            self.stdout.write(f"Found {len(users)} total users")

            # Identify target and users to delete
            target_user = None
            users_to_delete = []

            for user in users:
                email = user.email or user.user_metadata.get('email', '')
                display_name = user.user_metadata.get('full_name', '-')
                uid = user.id

                self.stdout.write(f"  - {display_name} ({email}) [UID: {uid}]")

                if display_name.lower() == 'deeksha' or email.lower() == 'meduraa.web@gmail.com':
                    target_user = (uid, email, display_name)
                else:
                    users_to_delete.append((uid, email, display_name))

            if not options['confirm']:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n{len(users_to_delete)} users will be DELETED. "
                        "Run with --confirm to proceed.\n"
                    )
                )
                return

            # Delete extra users
            if users_to_delete:
                self.stdout.write(
                    self.style.WARNING(f"\nDeleting {len(users_to_delete)} users...")
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
                # Optionally update password here if needed
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "\nWarning: No existing 'deeksha' admin found. "
                        "You may need to manually create it in Supabase with email "
                        "meduraa.web@gmail.com and password Kali2712@"
                    )
                )

            self.stdout.write(
                self.style.SUCCESS("\n✓ Cleanup complete!")
            )

        except Exception as e:
            raise CommandError(f"Supabase operation failed: {str(e)}")
