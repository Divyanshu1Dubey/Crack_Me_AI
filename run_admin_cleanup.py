#!/usr/bin/env python3
"""
FINAL ADMIN CLEANUP EXECUTION SCRIPT
This script attempts to:
1. Check for service role key in environment
2. Check for service role key in .env
3. Accept it as command line argument
4. Execute the cleanup automatically
"""
import os
import sys
import subprocess
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

def run_cleanup(service_role_key=None):
    """Execute the cleanup process"""
    
    backend_dir = Path(__file__).parent / 'backend'
    
    # Check for service role key from various sources
    if not service_role_key:
        # Try environment variable
        service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not service_role_key:
        # Try reading from .env
        env_file = backend_dir / '.env'
        if env_file.exists():
            with open(env_file, encoding='utf-8', errors='replace') as f:
                for line in f:
                    if line.startswith('SUPABASE_SERVICE_ROLE_KEY='):
                        service_role_key = line.split('=', 1)[1].strip()
                        if service_role_key != 'YOUR_SERVICE_ROLE_KEY_HERE':
                            break
    
    if not service_role_key or service_role_key == 'YOUR_SERVICE_ROLE_KEY_HERE':
        print("\n" + "="*70)
        print("SUPABASE ADMIN CLEANUP - EXECUTION BLOCKED")
        print("="*70)
        print("\n❌ SUPABASE_SERVICE_ROLE_KEY is not configured.")
        print("\nTo complete the cleanup, you MUST provide your service role key.")
        print("\nOPTION 1: Set environment variable")
        print("  $env:SUPABASE_SERVICE_ROLE_KEY='your_key_here'")
        print("  python run_admin_cleanup.py")
        print("\nOPTION 2: Pass as command line argument")
        print("  python run_admin_cleanup.py --key 'your_key_here'")
        print("\nOPTION 3: Edit backend/.env")
        print("  Open: backend/.env")
        print("  Find: SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY_HERE")
        print("  Replace with your actual key")
        print("  Then run: python run_admin_cleanup.py")
        print("\nTo get your service role key:")
        print("  1. Go to: https://supabase.com/dashboard")
        print("  2. Select project: ryuvcdthjnxyetdyjbph")
        print("  3. Settings → API")
        print("  4. Copy: Service Role Secret Key")
        print("\n" + "="*70 + "\n")
        return False
    
    # Set environment variable for cleanup script
    os.environ['SUPABASE_SERVICE_ROLE_KEY'] = service_role_key
    
    # Run cleanup_admins_auto.py
    cleanup_script = backend_dir / 'cleanup_admins_auto.py'
    
    print("\n" + "="*70)
    print("EXECUTING ADMIN CLEANUP")
    print("="*70 + "\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(cleanup_script)],
            cwd=str(backend_dir),
            env={**os.environ, 'SUPABASE_SERVICE_ROLE_KEY': service_role_key}
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running cleanup: {str(e)}")
        return False


if __name__ == '__main__':
    # Check for command line argument
    service_role_key = None
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--key' and len(sys.argv) > 2:
            service_role_key = sys.argv[2]
        elif sys.argv[1].startswith('--key='):
            service_role_key = sys.argv[1].split('=', 1)[1]
        elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("""
ADMIN CLEANUP EXECUTION SCRIPT

Usage:
  python run_admin_cleanup.py                    # Check .env for key
  python run_admin_cleanup.py --key YOUR_KEY     # Provide key directly
  
Environment:
  Set $env:SUPABASE_SERVICE_ROLE_KEY before running
  
.env File:
  Add SUPABASE_SERVICE_ROLE_KEY=your_key to backend/.env
            """)
            sys.exit(0)
    
    success = run_cleanup(service_role_key)
    sys.exit(0 if success else 1)
