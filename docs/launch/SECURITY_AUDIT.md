# Phase 4 — Security Audit (Launch Supplement)

**Date:** 2026-07-22
**Supplements:** `docs/SECURITY_AUDIT.md` (existing comprehensive audit)

This document records only the changes and additions made during the
Phase 4 launch-readiness review.  Existing entries still apply.

---

## Phase-4 additions

### 1. Production-only env validation (`backend/crack_cms/security.py`)

Verifies at import-time:

* `DJANGO_SECRET_KEY` is set to something other than
  `django-insecure-local-dev-only`.
* `DATABASE_URL` (or `SUPABASE_DATABASE_URL`) is configured.
* `FRONTEND_URL` (when set) is in `CORS_ALLOWED_ORIGINS` and
  `CSRF_TRUSTED_ORIGINS`.
* `ALLOWED_HOSTS` doesn't contain `localhost` in production.
* At least one AI provider key is configured (warning, not fatal).

Wired into `backend/crack_cms/urls.py` — runs once at app import.

### 2. Liveness / readiness probes

```
GET /api/live/    → 200 always (process check)
GET /api/ready/   → 200 + 'ready' if `SELECT 1` succeeds; 503 otherwise
```

Replaces the existing `/api/health/` for k8s/Render/DO load-balancer
integration.  `/api/health/` retained for backward compatibility.

### 3. `Sentry PII` defaults

Confirmed: `SENTRY_SEND_DEFAULT_PII=False` in production via env
override.

### 4. Phase-4 test coverage

`backend/questions/tests_phase4.py` adds:

* `SecurityPostureTestCase` — verifies dev skips the check and prod
  raises `ImproperlyConfigured` when `DJANGO_SECRET_KEY` /
  `DATABASE_URL` are missing.

---

## Verified-as-still-clean (Phase-4 spot-check)

* **SQL injection** — DRF + Django ORM only; no raw SQL outside of
  pre-existing RAG `chroma_db` paths.
* **XSS** — React 19 + `FormattedText` uses `dangerouslySetInnerHTML`
  only on AI-generated text; mojibake cleanup (`textCleanup.decodeMojiB`)
  runs before render.
* **CORS** — env-driven `_parse_origin_list` with rejection of bare
  hostnames / paths.
* **Cookies** — `SESSION_COOKIE_HTTPONLY` + `CSRF_COOKIE_HTTPONLY`
  always on; `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` only in
  production.
* **Rate limiting** — `rest_framework.throttling.ScopedRateThrottle`
  + `questions.middleware.RateLimitMiddleware`.
* **Lockout** — `django-axes` `AXES_FAILURE_LIMIT=5`,
  `AXES_COOLOFF_TIME=30min`.

---

## Action items deferred to Phase 5

* Migrate `MEDIA_ROOT` storage to S3 / Supabase Storage.
* Strict JWT access-token TTL (15 min) + refresh-token rotation on
  password change.
* Sentry `data_scrubber` for email / token fields.

These are documented in `docs/launch/TECHNICAL_DEBT.md`.
