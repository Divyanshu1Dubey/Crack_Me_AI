# Admin Cleanup Setup Complete ✓

## Summary

I've prepared a complete admin cleanup system for your Supabase project. Here's what's ready:

## 🎯 What Was Done

### 1. **Dependencies Added** 
- ✅ Added `supabase>=2.0` to `backend/requirements.txt`
- ✅ Installed supabase Python client in your virtual environment

### 2. **Cleanup Tools Created**

#### Interactive Script: `backend/cleanup_admins_interactive.py`
- User-friendly Python script
- Lists all Supabase auth users with their details
- Shows which admin will be kept (deeksha)
- Shows which admins will be deleted
- Asks for confirmation before deletion
- **Ready to run!**

**Command:**
```bash
cd backend
python cleanup_admins_interactive.py
```

#### Django Management Command: `backend/accounts/management/commands/cleanup_supabase_admins.py`
- Alternative command-line interface
- Integrates with Django
- Supports `--confirm` flag for automation

**Command:**
```bash
python manage.py cleanup_supabase_admins --service-role-key YOUR_KEY --confirm
```

### 3. **Configuration Updated**
- ✅ Updated `backend/.env` with Supabase URL and service role key placeholder
- ✅ Added clear comments pointing to where to get the key

### 4. **Documentation Created**
- ✅ `backend/ADMIN_CLEANUP_GUIDE.md` - Complete step-by-step guide

## ⚡ What You Need To Do

### Step 1: Get Your Service Role Key
1. Go to: https://supabase.com/dashboard
2. Select your project (ryuvcdthjnxyetdyjbph)
3. Go to: **Settings** → **API**
4. Copy the **Service Role Secret Key**

### Step 2: Add It To .env
Open `backend/.env` and replace:
```
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY_HERE
```

With your actual key.

### Step 3: Run The Cleanup
```bash
cd backend
python cleanup_admins_interactive.py
```

When prompted:
- Review the list of users
- Type `DELETE` to confirm cleanup
- Script will delete all admins except "deeksha"

## 📊 Expected Result

**Before Cleanup:**
- Multiple admin users (test, admin_live, admin_local, admin_shape, etc.)

**After Cleanup:**
- ✅ Single admin: `deeksha`
- ✅ Email: `meduraa.web@gmail.com`
- ✅ Password: `Kali2712@`

## 🔐 Security Notes

- **Service Role Key is SECRET** - Never commit to Git
- Only store in local `.env` (already in .gitignore)
- Use in secure/private environments only
- The cleanup is permanent - deleted users cannot be recovered

## 📁 Files Created/Modified

| File | Status |
|------|--------|
| `backend/requirements.txt` | ✅ Updated - supabase added |
| `backend/.env` | ✅ Updated - key placeholder added |
| `backend/cleanup_admins_interactive.py` | ✅ Created - Ready to use |
| `backend/accounts/management/commands/cleanup_supabase_admins.py` | ✅ Created - Ready to use |
| `backend/ADMIN_CLEANUP_GUIDE.md` | ✅ Created - Detailed guide |

## 🚀 Quick Start Command

```bash
# 1. Activate virtual environment
cd c:\Users\DIVYANSHU\Desktop\crack_cms
.\.venv\Scripts\Activate.ps1

# 2. Add your service role key to backend/.env
# (Replace YOUR_SERVICE_ROLE_KEY_HERE with actual key)

# 3. Run cleanup
cd backend
python cleanup_admins_interactive.py

# 4. When prompted, type: DELETE
```

## ✅ Ready!

Everything is set up and ready. Just provide your SUPABASE_SERVICE_ROLE_KEY and run the cleanup script!

---

**Questions?** Check `ADMIN_CLEANUP_GUIDE.md` for troubleshooting and detailed instructions.
