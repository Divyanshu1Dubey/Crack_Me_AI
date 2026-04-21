#!/usr/bin/env python3
"""
Supabase Admin Cleanup - Automated Version
This script attempts to clean up admins using available credentials
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')

import django
django.setup()

try:
    from supabase import create_client
    from supabase.lib.client_options import ClientOptions
except ImportError:
    print("❌ Supabase client not installed. Run: pip install supabase")
    sys.exit(1)


TARGET_EMAIL = "meduraa.web@gmail.com"
TARGET_NAME = "deeksha"
TARGET_PASSWORD = "Kali2712@"


def cleanup_admins_auto():
    """Auto cleanup using environment or input"""
    
    # Get Supabase credentials
    supabase_url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found in .env")
        return False
    
    print("\n" + "="*70)
    print("SUPABASE ADMIN CLEANUP - AUTOMATED MODE")
    print("="*70)
    print(f"\nSupabase Project: {supabase_url}\n")
    
    if not service_role_key or service_role_key == 'YOUR_SERVICE_ROLE_KEY_HERE':
        print("⚠️  SUPABASE_SERVICE_ROLE_KEY not configured in .env")
        print("\nTo complete the cleanup, you need to:")
        print("1. Go to: https://supabase.com/dashboard")
        print("2. Select your project (ryuvcdthjnxyetdyjbph)")
        print("3. Go to: Settings → API")
        print("4. Copy the 'Service Role Secret Key'")
        print("5. Add to backend/.env:")
        print("   SUPABASE_SERVICE_ROLE_KEY=<your_key_here>")
        print("\nThen run this script again.")
        return False
    
    try:
        print("🔗 Connecting to Supabase...\n")
        options_obj = ClientOptions(auto_refresh_token=False, persist_session=False)
        supabase = create_client(supabase_url, service_role_key, options=options_obj)
        
        # List all auth users
        print("📋 Fetching all auth users...")
        resp = supabase.auth.admin.list_users()
        users = resp.users if hasattr(resp, 'users') else resp
        if users is None:
            users = []
        
        print(f"📊 Found {len(users)} total users\n")
        print("User List:")
        print("-" * 70)
        
        target_user = None
        users_to_delete = []
        
        # Categorize users
        for i, user in enumerate(users, 1):
            email = user.email or user.user_metadata.get('email', 'N/A')
            display_name = user.user_metadata.get('full_name', '-')
            uid = user.id
            
            status = ""
            if email.lower() == TARGET_EMAIL:
                target_user = (uid, email, display_name)
                status = "  ← KEEP THIS ADMIN ✓"
            else:
                users_to_delete.append((uid, email, display_name))
                status = "  ← DELETE"
            
            print(f"{i}. {display_name:20} | {email:35}{status}")
        
        print("-" * 70)
        
        # Ensure the required admin exists and has expected profile/password.
        if target_user is None:
            print("\n➕ Creating required admin user...")
            created = supabase.auth.admin.create_user({
                "email": TARGET_EMAIL,
                "password": TARGET_PASSWORD,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": TARGET_NAME,
                    "first_name": TARGET_NAME,
                    "role": "admin",
                    "is_admin": True,
                },
            })
            created_user = created.user if hasattr(created, "user") else created
            target_user = (
                getattr(created_user, "id", None),
                getattr(created_user, "email", TARGET_EMAIL),
                TARGET_NAME,
            )
            print(f"✅ Created admin: {TARGET_NAME} ({TARGET_EMAIL})")
        else:
            # Make target admin metadata and password deterministic.
            print("\n🛠️  Updating required admin profile/password...")
            supabase.auth.admin.update_user_by_id(
                target_user[0],
                {
                    "password": TARGET_PASSWORD,
                    "user_metadata": {
                        "full_name": TARGET_NAME,
                        "first_name": TARGET_NAME,
                        "role": "admin",
                        "is_admin": True,
                    },
                },
            )
            target_user = (target_user[0], TARGET_EMAIL, TARGET_NAME)

        if not users_to_delete:
            print("\n✅ Only required admin exists. No cleanup needed!")
            print(f"   - Single admin remaining: {TARGET_NAME} ({TARGET_EMAIL})")
            return True
        
        # Show deletion plan
        print(f"\n⚠️  DELETION PLAN:")
        print(f"   - Keep: {target_user[2] if target_user else 'NONE'} ({target_user[1] if target_user else 'NONE'})")
        print(f"   - Delete: {len(users_to_delete)} user(s)")
        print(f"\nDeleting the following users:")
        for uid, email, name in users_to_delete:
            print(f"   ✗ {name} ({email})")
        
        # Delete extra users
        print(f"\n🗑️  Deleting {len(users_to_delete)} user(s)...\n")
        
        deleted_count = 0
        failed_count = 0
        
        for uid, email, name in users_to_delete:
            try:
                supabase.auth.admin.delete_user(uid)
                print(f"  ✓ Deleted: {name:20} ({email})")
                deleted_count += 1
            except Exception as e:
                print(f"  ✗ Failed:  {name:20} - {str(e)}")
                failed_count += 1
        
        print(f"\n{'='*70}")
        print(f"✅ CLEANUP COMPLETE!")
        print(f"   - Deleted: {deleted_count} user(s)")
        print(f"   - Failed: {failed_count} user(s)")
        if target_user:
            print(f"   - Single admin remaining: {target_user[2]} ({target_user[1]})")
        print(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = cleanup_admins_auto()
    sys.exit(0 if success else 1)
