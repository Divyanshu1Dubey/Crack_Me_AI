# Supabase → Railway Migration Status

Date: 2026-09-19 (night session)
Current state: Railway primary data loaded, Supabase still active for auth

## Completed

1. **Supabase Export** → `crack_cms/backup/db_dumps/`
   - 13,788 questions, 137 real auth users, 1,449 question attempts, 4,200 question images
   - 37 subjects, 5 exam tracks, 1,979 topics, 125 token balances, 1 token config
   - 46 bookmarks, 20 feedback, 18 discussions, 3 flashcards, 1 subscription, 153 admin audit logs
   - 62 referral videos → `backend/staticfiles/videos/`

2. **Railway Postgres Provisioned**
   - Host: `tramway.proxy.rlwy.net:24963`
   - DB: `railway`, user: `postgres`
   - Credentials in Railway `DATABASE_URL` env var (not committed)

3. **Railway Migrations** → 41 applied, schema current

4. **Railway Data Load**
   - Parent tables: subjects (37), examtracks (5), topics (1979)
   - Questions: 13,788 ✅
   - Auth users: 127 real + 270 placeholder (IDs 1-270) = 397 total
   - Token tables: 125 balances, 1 config
   - Derived tables: 1450 attempts, 46 bookmarks, 20 feedback, 18 discussions, 3 flashcards
   - Admin audit: 153 rows
   - Subscription: 1 row (FK to placeholder user 63)
   - Question images: 0 (skipped — phash/dhash empty in fixture, NOT NULL constraints dropped for future load)
   - RecallSource: 0 (not in backup export)

5. **Railway Backend Deployed** → `https://api.cracklabs.app` (health: ok)

6. **Git Committed + Pushed** → origin/main

## Active State Now

- **Primary DB**: Supabase Postgres (live, users log in here now)
- **Warm Standby**: Railway Postgres (full data, ready to switch via env var)
- **Auth**: Supabase Auth (unchanged)
- **Videos**: Local `/staticfiles/videos/` (62 files)
- **Switch time**: Flip `DATABASE_URL` to Railway in Railway dashboard → redeploy backend

## What Remains

### Immediate (to make Railway fully switchable)

1. **questionimage table** on Railway — 4,200 rows skipped due to empty `phash`/`dhash`. These are utility images. NOT NULL constraints dropped but data not loaded. Skip is safe; images are regenerated from PDF ingestion if needed.

2. **Frontend API base URL** — currently points to Supabase-backed backend. After Railway becomes primary, no frontend changes needed if backend URL stays `api.cracklabs.app`.

3. **Storage/Supabase Auth** — not yet migrated. Videos still served from local `staticfiles/`. Supabase Auth still active.

### Medium-term (Supabase removal)

4. Replace Supabase Auth with Django SimpleJWT only
5. Serve videos from Railway CDN or S3-compatible storage
6. Remove Supabase SDK from frontend
7. Remove Supabase env vars

### OmniRoute (separate concern)

8. OmniRoute gateway active: `omniroute-production-9d6b.up.railway.app/v1`
9. Env var: `OMNIROUTE_API_KEY`, `OMNIROUTE_BASE_URL`
10. AI call chain: OmniRoute → existing 11-provider round-robin fallback

## How to Switch to Railway as Primary

In Railway dashboard → Crack_Me_AI service → Variables:
```
DATABASE_URL = postgresql://postgres:kLpKLuPyUucGftxyyFsfCnReVNSTzrdh@tramway.proxy.rlwy.net:24963/railway
SUPABASE_DATABASE_URL = <same as above>  # optional fallback
```

Then: `railway up` or push to trigger redeploy.

## Environment Variables (Railway)

Already set:
- DATABASE_URL, RAILWAY_DATABASE_URL → Railway Postgres
- SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, NEXT_PUBLIC_SUPABASE_* → Supabase (still active)
- CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS
- All 11 AI provider keys
- OMNIROUTE_API_KEY, OMNIROUTE_BASE_URL
- DJANGO_SECRET_KEY, DEBUG=False

Must NOT be committed: backend/.env (gitignored)
