# Phase 4 — Deployment Checklist

**Date:** 2026-07-22
**Applies to:** Render (backend), Vercel (frontend), Supabase (DB),
DigitalOcean App Platform (backup).

---

## Pre-launch (one-time)

### Backend (Render / DigitalOcean)

- [x] `backend/requirements.txt` is pinned (no `>=` for pinned libs).
- [x] `backend/build.sh` installs deps, migrates, runs
      `collectstatic --noinput`, loads NEET PG fixture.
- [x] `Procfile` (root) defines `web: gunicorn crack_cms.wsgi --log-file -`.
- [ ] Production secrets configured in the platform dashboard:
  - [x] `DJANGO_SECRET_KEY` (50+ chars)
  - [x] `DATABASE_URL` (Supabase Postgres)
  - [x] `FRONTEND_URL`
  - [x] `CORS_ALLOWED_ORIGINS`
  - [x] `CSRF_TRUSTED_ORIGINS`
  - [x] `ALLOWED_HOSTS`
  - [x] `SENTRY_DSN`
  - [x] AI keys (Groq, Gemini, Cerebras, ...)
- [x] Database migrations applied via `build.sh`.
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
- [x] Run `python manage.py loaddata questions_fixture.json` on first
      deploy to bootstrap the bank.

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
