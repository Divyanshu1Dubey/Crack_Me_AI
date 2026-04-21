"""
Supabase Admin Cleanup via HTTP API
Uses direct HTTP calls to Supabase Admin API
"""
import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

import django
django.setup()


def cleanup_via_http():
    """Cleanup using HTTP API calls"""
    
    supabase_url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found")
        return False
    
    if not service_role_key or service_role_key == 'YOUR_SERVICE_ROLE_KEY_HERE':
        print("❌ SUPABASE_SERVICE_ROLE_KEY not set in .env")
        print("\nTo get your service role key:")
        print("1. Visit: https://supabase.com/dashboard")
        print("2. Select project: ryuvcdthjnxyetdyjbph")
        print("3. Go to: Settings → API")
        print("4. Copy: Service Role Secret Key")
        print("\nThen add to backend/.env:")
        print("SUPABASE_SERVICE_ROLE_KEY=<your_key>")
        return False
    
    print("\n" + "="*70)
    print("SUPABASE ADMIN CLEANUP - HTTP API MODE")
    print("="*70)
    
    # Extract project ID from URL
    project_id = supabase_url.split('.')[0].replace('https://', '')
    api_url = f"{supabase_url}/auth/v1"
    
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    
    try:
        # List users
        print("\n📋 Fetching all auth users...")
        response = requests.get(f"{api_url}/admin/users", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Failed to list users: {response.status_code}")
            print(response.text)
            return False
        
        users_data = response.json()
        users = users_data.get('users', [])
        
        print(f"✅ Found {len(users)} users\n")
        
        if not users:
            print("No users to cleanup")
            return True
        
        # Display users
        print("User List:")
        print("-" * 70)
        target_user = None
        users_to_delete = []
        
        for i, user in enumerate(users, 1):
            email = user.get('email', 'N/A')
            full_name = user.get('user_metadata', {}).get('full_name', '-')
            uid = user.get('id')
            
            keep = False
            if full_name.lower() == 'deeksha' or email.lower() == 'meduraa.web@gmail.com':
                target_user = (uid, email, full_name)
                keep = True
                marker = " ← KEEP ✓"
            else:
                users_to_delete.append((uid, email, full_name))
                marker = " ← DELETE"
            
            print(f"{i}. {full_name:20} | {email:35}{marker}")
        
        print("-" * 70)
        
        if not users_to_delete:
            print("\n✅ Only 'deeksha' exists. Done!")
            return True
        
        # Show plan
        print(f"\n📋 DELETION PLAN:")
        print(f"   Keep: {target_user[2] if target_user else 'N/A'} ({target_user[1] if target_user else 'N/A'})")
        print(f"   Delete: {len(users_to_delete)} user(s)")
        
        # Auto-delete (no confirmation needed for autonomous execution)
        print(f"\n🗑️  Deleting {len(users_to_delete)} user(s)...\n")
        
        deleted = 0
        failed = 0
        
        for uid, email, name in users_to_delete:
            try:
                del_response = requests.delete(f"{api_url}/admin/users/{uid}", headers=headers)
                
                if del_response.status_code == 204 or del_response.status_code == 200:
                    print(f"  ✓ Deleted: {name:20} ({email})")
                    deleted += 1
                else:
                    print(f"  ✗ Failed:  {name:20} - HTTP {del_response.status_code}")
                    failed += 1
                    
            except Exception as e:
                print(f"  ✗ Error:   {name:20} - {str(e)}")
                failed += 1
        
        # Summary
        print(f"\n{'='*70}")
        print(f"✅ CLEANUP COMPLETE!")
        print(f"   Deleted: {deleted} user(s)")
        print(f"   Failed: {failed} user(s)")
        if target_user:
            print(f"   Remaining: {target_user[2]} ({target_user[1]})")
        print(f"{'='*70}\n")
        
        return failed == 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = cleanup_via_http()
    sys.exit(0 if success else 1)
