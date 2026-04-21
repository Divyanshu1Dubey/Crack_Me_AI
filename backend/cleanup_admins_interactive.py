"""
Direct Supabase admin cleanup script
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')

import django
django.setup()

from supabase import create_client
from supabase.lib.client_options import ClientOptions


def cleanup_admins():
    # Get Supabase credentials
    supabase_url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found in .env")
        return
    
    # Ask for service role key
    print("\n" + "="*60)
    print("SUPABASE ADMIN CLEANUP TOOL")
    print("="*60)
    print(f"\nSupabase Project: {supabase_url}")
    
    service_role_key = input("\nEnter your SUPABASE_SERVICE_ROLE_KEY: ").strip()
    
    if not service_role_key:
        print("❌ Service role key is required")
        return
    
    try:
        print("\n🔗 Connecting to Supabase...")
        options_obj = ClientOptions(auto_refresh_token=False, persist_session=False)
        supabase = create_client(supabase_url, service_role_key, options=options_obj)
        
        # List all auth users
        print("📋 Fetching all auth users...")
        resp = supabase.auth.admin.list_users()
        users = resp.users if hasattr(resp, 'users') else resp
        
        if not users:
            print("✅ No users found in Supabase auth")
            return
        
        print(f"\n📊 Found {len(users)} total users:\n")
        
        target_user = None
        users_to_delete = []
        
        # Categorize users
        for user in users:
            email = user.email or user.user_metadata.get('email', 'N/A')
            display_name = user.user_metadata.get('full_name', '-')
            uid = user.id
            
            print(f"  • {display_name:20} | {email:35} | {uid[:12]}...")
            
            # Identify target user
            if display_name.lower() == 'deeksha' or email.lower() == 'meduraa.web@gmail.com':
                target_user = (uid, email, display_name)
                print(f"    → KEEPING THIS ADMIN ✓")
            else:
                users_to_delete.append((uid, email, display_name))
        
        if not users_to_delete:
            print("\n✅ Only 'deeksha' admin exists. No cleanup needed!")
            return
        
        # Confirm deletion
        print(f"\n⚠️  ACTION: Delete {len(users_to_delete)} user(s) and keep only 'deeksha'")
        confirm = input("Type 'DELETE' to proceed (or anything else to cancel): ").strip()
        
        if confirm != 'DELETE':
            print("❌ Cleanup cancelled")
            return
        
        # Delete extra users
        print(f"\n🗑️  Deleting {len(users_to_delete)} user(s)...\n")
        
        for uid, email, name in users_to_delete:
            try:
                supabase.auth.admin.delete_user(uid)
                print(f"  ✓ Deleted: {name:20} ({email})")
            except Exception as e:
                print(f"  ✗ Failed: {name:20} - {str(e)}")
        
        print(f"\n✅ CLEANUP COMPLETE!")
        if target_user:
            uid, email, name = target_user
            print(f"   Single admin remaining: {name} ({email})")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    cleanup_admins()
