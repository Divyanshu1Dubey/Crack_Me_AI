# Supabase Admin Cleanup Guide

## Overview
This guide will help you clean up duplicate admin users in your Supabase project and leave only the `deeksha` admin account.

## Current Status

✅ **Completed:**
- Created interactive cleanup script: `cleanup_admins_interactive.py`
- Added Supabase Python client to requirements.txt
- Set up Django management command: `cleanup_supabase_admins.py`
- Updated backend .env with Supabase URL and placeholder for service role key

❌ **Blocked On:**
- `SUPABASE_SERVICE_ROLE_KEY` - Required to delete users from Supabase Auth

## How to Get Your Service Role Key

1. Go to your [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project: `https://ryuvcdthjnxyetdyjbph.supabase.co`
3. Navigate to: **Settings** → **API**
4. Look for **Service Role Secret Key** section
5. Copy the full key (it starts with `eyJ...` or similar)

⚠️ **Security Warning**: This is a secret key! Never commit it to Git or share publicly.

## Method 1: Using the Interactive Script (Recommended)

### Steps:

1. **Activate the virtual environment:**
   ```bash
   cd c:\Users\DIVYANSHU\Desktop\crack_cms
   .\.venv\Scripts\Activate.ps1
   ```

2. **Update .env with your service role key:**
   - Open `backend\.env`
   - Find line: `SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY_HERE`
   - Replace `YOUR_SERVICE_ROLE_KEY_HERE` with your actual key

3. **Run the cleanup script:**
   ```bash
   cd backend
   python cleanup_admins_interactive.py
   ```

4. **The script will:**
   - List all Supabase auth users
   - Identify the `deeksha` admin to keep
   - Show all other users that will be deleted
   - Ask for confirmation (type `DELETE` to proceed)
   - Delete all extra users
   - Keep only the `deeksha` admin

## Method 2: Using Django Management Command

If you prefer using Django's management system:

```bash
cd backend
python manage.py cleanup_supabase_admins \
  --service-role-key "YOUR_SERVICE_ROLE_KEY_HERE" \
  --confirm
```

## What Happens After Cleanup

After successful cleanup, you'll have:

### Single Admin Account:
- **Name:** deeksha
- **Email:** meduraa.web@gmail.com  
- **Password:** Kali2712@

### Deleted Users:
All other users in Supabase auth will be permanently deleted.

## Troubleshooting

### "Service Role Key NOT found"
- Check that `SUPABASE_SERVICE_ROLE_KEY` is in `backend\.env`
- Verify it's not wrapped in quotes

### "ModuleNotFoundError: No module named 'supabase'"
- Make sure virtual environment is activated
- Run: `pip install supabase`

### "Connection refused" or timeout
- Verify your internet connection
- Check that Supabase URL is correct: `https://ryuvcdthjnxyetdyjbph.supabase.co`

### "Unauthorized" error
- Double-check your service role key
- Make sure you copied the full key (very long string)
- Ensure there are no extra spaces

## Files Created/Modified

| File | Purpose |
|------|---------|
| `backend/cleanup_admins_interactive.py` | Interactive admin cleanup script |
| `backend/accounts/management/commands/cleanup_supabase_admins.py` | Django management command |
| `backend/requirements.txt` | Added `supabase>=2.0` dependency |
| `backend/.env` | Added SUPABASE_SERVICE_ROLE_KEY placeholder |

## Next Steps

1. **Get your service role key** from Supabase Dashboard
2. **Add it to** `backend/.env`  
3. **Run** `python cleanup_admins_interactive.py`
4. **Confirm** when prompted
5. **Done!** Only `deeksha` admin will remain

---

**Need help?** Check the terminal output for specific error messages.
