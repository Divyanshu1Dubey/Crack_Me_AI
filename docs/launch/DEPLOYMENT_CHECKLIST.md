# Phase 4 — Deployment Checklist

**Date:** 2026-07-22
**Applies to:** Render (backend), Vercel (frontend), Supabase (DB),
DigitalOcean App Platform (backup).

---

## Pre-launch (one-time)

### Backend (Render / DigitalOcean)

- [x] `backend/requirements.txt` is pinned (no `>=` for pinned libs).
- [x] `backend/build.sh` installs deps, runs `collectstatic --no-input`,
      migrates, prints the `link_supabase_identity --all-privileged` dry run,
      seeds an empty CMS bank (`seed_question_bank`) and runs the idempotent
      KB / blog steps. It no longer runs `import_neet_pg` and never runs
      destructive data commands (full order: [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §7).
- [x] `backend/Procfile` defines `release: python manage.py migrate --no-input`,
      `web: python manage.py migrate --no-input && gunicorn crack_cms.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 4 --timeout 120 --log-file -`
      (migrates first: platforms such as Railway never run the `release` line) and
      `worker: python manage.py qcluster`.
- [ ] **Worker component** running `python manage.py qcluster` with the web
      component's environment. DigitalOcean App Platform does not start the
      Procfile `worker` (or run `release`) by itself. Without it, ingestion /
      recall imports and video jobs stay queued, renewal reminders are never
      sent and the `ingestion_recover_stale_jobs` sweeper (django-q Schedule,
      every 10 min, created by `migrate`) never runs.
- [ ] Media: Django serves `/media/` only with `DEBUG=True`. Serve
      `MEDIA_ROOT` at `/media/` from the platform (persistent volume) or move
      media to a bucket, or MEDIA-linked files such as textbook page
      screenshots (`/api/ai/screenshot/<id>/` → `screenshot_url`) do not load.
- [ ] Production secrets configured in the platform dashboard:
  - [x] `DJANGO_SECRET_KEY` (50+ chars)
  - [x] `DATABASE_URL` (Supabase Postgres)
  - [x] `FRONTEND_URL`
  - [x] `CORS_ALLOWED_ORIGINS`
  - [x] `CSRF_TRUSTED_ORIGINS`
  - [x] `ALLOWED_HOSTS`
  - [x] `SENTRY_DSN`
  - [x] AI keys (Groq, Gemini, Cerebras, ...)
  - [ ] `SUPABASE_URL`, `SUPABASE_ANON_KEY` (public key for token
        verification; `accounts.W002` without it), `SUPABASE_SERVICE_ROLE_KEY`
        (admin tooling)
  - [ ] `SUPABASE_EMAIL_CONFIRMATION_ENABLED=true` — only after Supabase
        → Authentication → Sign In / Providers → Email has **"Confirm email"
        ON and "Secure email change" ON** (`accounts.W001` until then)
  - [ ] `CORE_DATA_BACKUP_PATH` on a persistent volume (`accounts.W003`;
        admin Backup / Restore answer `503 backup_not_configured` without it)
  - [ ] `NUM_PROXIES` and `TRUSTED_CLIENT_IP_HEADER` (DigitalOcean:
        `DO-Connecting-IP`): check as an admin with `GET /api/health/client-ip/`
        which headers reach Django, and that a forged one does not
- [ ] `python manage.py check --deploy` shows no `accounts.W00x` warning.
- [x] Database migrations applied via `build.sh`.

### One-time owner steps (never run by `build.sh`)

- [ ] After `accounts.0023` (Supabase uid linking):
      `python manage.py link_supabase_identity --all-privileged` (dry run),
      review the `CHECK` rows, then `--all-privileged --apply`
      (see [`../AUTHENTICATION.md`](../AUTHENTICATION.md) §4.1).
- [ ] Databases that ran the old `import_neet_pg` deploy step:
      `python manage.py import_neet_pg --replace --dry-run`, review, then
      `python manage.py import_neet_pg --replace`.
- [ ] Databases from releases before the `seed_data` fix:
      `python manage.py cleanup_seed_samples`, review, then `--apply`.
- [ ] Leftover placeholder job listings: `python seed_jobs.py`
      (report), then `python seed_jobs.py --delete-placeholders`.
- [x] `MEDIA_ROOT` storage (currently local disk — see
      `TECHNICAL_DEBT.md` for the S3 migration).

### Frontend (Vercel)

- [x] `frontend/vercel.json` security headers.
- [x] `NEXT_PUBLIC_API_URL` set to the canonical DigitalOcean URL.
- [x] `NEXT_PUBLIC_API_FALLBACK_URL` set.
- [x] Supabase URL + anon key.

### Database (Supabase)

- [x] `DATABASE_URL` SSL mode `require` (production runtime sets
      `sslmode=require` automatically).
- [x] `db_connect_timeout=5` enforced.
- [x] A fresh database gets its CMS bank automatically: `build.sh` runs
      `seed_question_bank` (loads `backend/fixtures/cms_fixture.json` only
      while the bank is empty). `questions_fixture.json` no longer exists.

---

## Health checks

- [x] `GET /api/live/` — liveness probe (always 200).
- [x] `GET /api/ready/` — readiness probe (503 if `SELECT 1` fails).
- [x] `GET /api/health/` — legacy alias kept for backward compatibility.

Configure your platform's health-check URL to `/api/ready/`.

## Logging

- [x] JSON formatter when `DEBUG=False` (production).
- [x] `Sentry` DSN integration.
- [x] `ai_engine` logger DEBUG in dev, INFO in prod.

## Monitoring

- [x] `DATADOG_INIT` fires from `DatadogInit` component (frontend).
- [x] `TrafficAnalytics` component (frontend).
- [x] Recommendation: enable
  [Sentry Performance](https://sentry.io/for/performance/) (already
  integrated) — set `SENTRY_TRACES_SAMPLE_RATE=0.1` in production.

## Backups

- [x] Supabase Postgres PITR enabled (per Supabase default).
- [ ] Recommend enabling daily logical dumps → S3 in Phase 5.

## Cloudflare compatibility

- [x] `Cache-Control` headers (Vercel fronts CDN, headers set in
      `vercel.json`).
- [x] `Strict-Transport-Security` (HSTS) on (1 year, prod-only).
- [x] `X-Frame-Options: DENY`.
- [x] `Referrer-Policy: strict-origin-when-cross-origin`.

## Compression

- [x] `whitenoise` static-files compression (ManifestStaticFilesStorage).
- [ ] Gzip/Brotli at the CDN edge — already done by Vercel + Cloudflare
      defaults.

## Caching

- [x] Redis configured via `REDIS_URL` (django-redis back-end).
- [x] 60s cache on `recall_search` and `dashboard_v3`.
- [x] 24h cache on AI per-question features.

## Static assets

- [x] WhiteNoise static-files storage with hashed filenames.

## Media

- [x] `MEDIA_ROOT` = `backend/media`.
- [ ] S3 migration recommended in Phase 5.

---

## Disaster recovery

- [ ] Phase-5: schedule daily logical backups to S3.
- [ ] Phase-5: store a known-good backup locally for the SQL fixture.
- [x] Supabase PITR provides 7-day restore window.

---

## Roll-back plan

If a deploy fails:

1. Revert the release in Render / Vercel.
2. Database migrations are forward-only; if a migration needs to be
   reverted, write a new migration that reverses it (don't squash).
3. The importer is forward-only (additive) — re-runs are idempotent.
4. Cache: Redis is the only shared state; restart Redis or run
   `redis-cli FLUSHDB`.
