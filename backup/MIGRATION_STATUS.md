# Supabase → Railway Migration Status

**Date:** 2026-09-19
**Strategy:** Dual-run — Supabase stays primary, Railway is warm standby

## ✅ COMPLETED

### Phase 1: Complete Backup (286 MB total)

> 2026-11-01: `backup/db_dumps/`, the user-table SQL dumps in `backup/sql/` and
> `backup/supabase_auth_users.json` were removed from the repository (personal
> data) and are gitignored. Keep such backups encrypted, outside the repo.

**Database exports** (in `backup/db_dumps/`):
- `questions.question.json` — 13,788 questions (33.9 MB)
- `questions.questionattempt.json` — 1,449 test attempts (284 KB)
- `questions.questionimage.json` — 4,200 images (3.6 MB)
- `questions.topic.json` — 1,979 topics (478 KB)
- `questions.questionbookmark.json` — 46 bookmarks
- `questions.questionfeedback.json` — 20 feedback items
- `questions.discussion.json` — 18 discussions
- `questions.flashcard.json` — 3 flashcards
- `questions.examtrack.json` — 5 exam tracks
- `questions.subject.json` — 37 subjects
- `accounts.customuser.json` — all users (from earlier dump)
- `accounts.tokenbalance.json` — token balances
- `accounts.subscription.json` — subscriptions
- `accounts.adminauditlog.json` — audit logs
- + More tables in `django_full_dump.json` (104 KB)

**Supabase Auth users:**
- `backup/supabase_auth_users.json` — 137 Supabase Auth users (143 KB)

**Storage files:**
- `backup/supabase_storage_videos/` — 62 educational videos (248 MB)
- `backup/supabase_storage_images/` — question images (1 found via API)

**Export scripts** (run from `backend/`):
- `backend/scripts/_export_tables.py --output-dir <dir>` — re-runnable export for all key tables
- `backend/scripts/_export_questions.py`, `_backup_export.py` and `_export_all_tables.py` — the same `--output-dir <dir>` contract
- `backend/scripts/_download_storage.py` — re-runnable storage download

`--output-dir` is required and must be **outside the repository** (and outside
any git working tree): the dumps hold user data, and the scripts refuse a path
inside a checkout (`backend/scripts/_safe_paths.py`).

### Phase 2: Railway Postgres Setup

**Railway Postgres created:**
- Project: `Postgres`
- Connection URL: `postgresql://postgres:<RAILWAY_DB_PASSWORD>@tramway.proxy.rlwy.net:24963/railway`
- Internal: `postgres.railway.internal:5432`

**Railway Backend updated:**
- `DATABASE_URL` now points to Railway Postgres
- `RAILWAY_DATABASE_URL` also set (same URL)
- Deployed successfully: https://api.cracklabs.app ✅
- Health check: `{"status": "ok"}` ✅
- **Railway Postgres is EMPTY** (no data yet — migrations still running)

**Railway Volume:**
- CLI has a bug with `--mount-path` flag (still investigating)
- Need to create volume via Railway dashboard for media files

## ⏳ IN PROGRESS

### Phase 2 (continued): Data Migration to Railway

**Migrations:** Running via `railway run -s Crack_Me_AI -- python manage.py migrate`
- This runs migrations locally but with Railway's DATABASE_URL env var
- Takes 5-10 minutes over internet connection to Railway Postgres

**Next: Load backup data into Railway Postgres**
```bash
# After migrations complete (the dump directory is outside the repository):
cd backend
python scripts/_export_tables.py --output-dir <dump dir outside the repo>
railway run -s Crack_Me_AI -- python scripts/_import_to_railway.py --input-dir <same dump dir>
```

## 📋 REMAINING WORK (when you want to cut over)

### 1. Create Railway Volume for Media Files
- Go to Railway dashboard → CMS project → Volumes → Add Volume
- Mount path: `/app/media`
- Upload video files from `backup/supabase_storage_videos/` to Railway Volume

### 2. Update Django Settings for Media
```python
# In settings.py, add:
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media/'
```

### 3. Load Backup Data to Railway Postgres
`backend/scripts/_import_to_railway.py` reads the `<app>.<model>.json` dumps
(parents before children, skipping FK violations). `--input-dir` is required:
the directory `_export_tables.py --output-dir` wrote, outside the repository.
```bash
cd backend
railway run -s Crack_Me_AI -- python scripts/_import_to_railway.py --input-dir <dump dir outside the repo>
```

To restore a questions backup (Django fixture JSON) instead, pass its path:
```bash
python scripts/restore_backup.py <path to the backup file, outside the repository>
```
It leaves admin-edited questions alone. (It used to read
`backend/questions_backup.json`, a tracked copy of a dump with student data.)

### 4. Point Railway Domain to Railway Postgres (Cutover)
When ready to switch from Supabase to Railway:
```bash
# Update Railway env var (already done, just verify):
railway variables --set DATABASE_URL="postgresql://postgres:PASSWORD@tramway.proxy.rlwy.net:24963/railway" -s Crack_Me_AI

# Remove Supabase connection strings:
railway variables --remove SUPABASE_URL -s Crack_Me_AI
railway variables --remove SUPABASE_SERVICE_ROLE_KEY -s Crack_Me_AI
```

### 5. Code Changes for Supabase → Django JWT Migration
See detailed plan in previous message. Requires changes to:
- `backend/accounts/supabase_rest_auth.py` → Replace with SimpleJWT
- `backend/accounts/supabase_auth.py` → Delete (mirror no longer needed)
- `backend/accounts/views.py` → Re-enable login/register endpoints
- `frontend/src/lib/auth.tsx` → Rewrite with JWT
- `frontend/src/lib/api.ts` → Replace Supabase interceptor
- `frontend/src/utils/supabase/` → Delete
- `frontend/middleware.ts` → Rewrite without Supabase
- Remove `@supabase/ssr` and `@supabase/supabase-js` from package.json

## 🚀 Quick Cutover Procedure (when needed)

If Supabase restricts your account:

**Option A: Quick Switch to Railway (keeps Supabase Auth temporarily)**
1. Railway already has Railway Postgres connected
2. Load backup data into Railway Postgres
3. Update Railway `DATABASE_URL` to Railway Postgres URL (already done)
4. Deploy to Railway
5. **Railway now serves your app with Railway Postgres**
6. Supabase Auth still validates JWTs — if it's down, users can't log in

**Option B: Full Independence (recommended)**
1. Complete steps 1-5 from Option A
2. Implement Django SimpleJWT auth (see code changes above)
3. Deploy updated code
4. **Railway is now 100% independent of Supabase**

## 📁 Backup Location
In the repository's `backup/` folder only:
- `supabase_storage_videos/` — 62 educational videos (248 MB)
- `sql/` — `copy_questionimage.sql` + `questionimage.csv` (question-image rows; the user-table dumps were removed)

(`supabase_storage_images/` is not in the repository.)

The database dumps (`db_dumps/`) and `supabase_auth_users.json` were removed
from the repository on 2026-11-01 (personal data). New dumps go to the
`--output-dir` given to the export scripts, outside the repository, kept
encrypted.

## 🔑 Important Credentials (saved for reference)

> Passwords removed 2026-11-01. They were committed to git history and must be
> rotated; keep credentials in the platform's environment settings only.

**Railway Postgres:**
- URL: `postgresql://postgres:<RAILWAY_DB_PASSWORD>@tramway.proxy.rlwy.net:24963/railway`
- Project ID: `10078c0e-2f4b-404d-aaf4-7c4bd2744d06`
- Volume ID: `bc9ad1c5-0a9d-4e80-8f4b-c88cf45834e5`

**Railway Backend:**
- Project ID: `3548fb00-16c8-48e5-b269-83c7ee039423`
- Service ID: `f45e7ea1-899f-404b-923f-54a831ee2206`
- URL: https://api.cracklabs.app

**Supabase (current, keep as backup):**
- Project: `ryuvcdthjnxyetdyjbph`
- URL: `https://ryuvcdthjnxyetdyjbph.supabase.co`
- DB: `postgresql://postgres.ryuvcdthjnxyetdyjbph:<SUPABASE_DB_PASSWORD>@aws-1-ap-south-1.pooler.supabase.com:5432/postgres`
