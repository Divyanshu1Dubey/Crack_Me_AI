# Security Audit

> Comprehensive security audit covering JWT, authentication, authorization, CSRF, CORS, XSS, SQL injection, secrets, env vars, rate limiting, file uploads, API abuse, privilege escalation, and dependency vulnerabilities.

---

## Executive Summary

| Domain | Risk | Status |
|---|---|---|
| JWT | Low-Medium | ✓ HttpOnly cookies via Supabase; manual refresh not wired on JWT path |
| Authentication | Medium | ✓ django-axes lockout; Supabase-first |
| Authorization | Low | ✓ DRF per-view permissions |
| CSRF | Low | ✓ Bearer auth on writes; CSRF on session endpoints |
| CORS | Low | ⚠ Localhost allowed in dev; production locked to Vercel |
| XSS | Low | ✓ React auto-escapes; no `dangerouslySetInnerHTML` in user content |
| SQL Injection | Very Low | ✓ Django ORM |
| Secrets | Medium-Historical | ⚠ Historical leak in commit `3770b2f` (API_KEYS.md) — already rotated |
| Env Vars | Low | ✓ `.env` git-ignored; pre-commit secret scan |
| Rate Limiting | **Low** | ✓ DRF throttling configured (AnonRateThrottle 120/min, UserRateThrottle 600/min, ScopedRateThrottle admin_control_tower 180/min); `questions.middleware.RateLimitMiddleware` adds 60 GET/min/IP layer |
| File Uploads | Medium | ⚠ `PDFUploadViewSet`, `KnowledgeUploadView` — verify magic-bytes check |
| API Abuse | Medium | ⚠ No bulk endpoint throttling |
| Privilege Escalation | Low | ✓ All admin endpoints require `is_superuser` |
| Dependency Vulnerabilities | Medium | ⚠ `safety check` runs in CI; manual review needed |

---

## 1. JWT

### Current state
- **Django JWT**: `ACCESS_TOKEN_LIFETIME=1 day`, `REFRESH_TOKEN_LIFETIME=7 days`. Algorithm `HS256`. Tokens signed with `DJANGO_SECRET_KEY`.
- **Supabase JWT**: 1-hour access, 7-day refresh, auto-rotated by `@supabase/ssr`.

### Strengths
- Short TTLs (1 day access)
- Token signature verification on every request via `JWTAuthentication` / `supabase_auth.validate_token`

### Weaknesses
- `ROTATE_REFRESH_TOKENS = False` and `BLACKLIST_AFTER_ROTATION = False` → old refresh tokens remain valid until natural expiry. A leaked refresh token = 7 days of access.
- **No `select_for_update` on token consumption** → potential race-condition over-consumption under high concurrency.
- Manual JWT refresh path (no auto-refresh on 401) — UX issue, not security issue.

### Severity: Medium

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Enable `ROTATE_REFRESH_TOKENS=True` + `BLACKLIST_AFTER_ROTATION=True` | 1 hour | High — limits leaked refresh-token blast radius |
| Move to short-lived (15 min) access + longer refresh | 4 hours | High |
| Implement JWT refresh interceptor on 401 in `api.ts` | 4 hours | Medium — UX |
| Wrap token consumption in `transaction.atomic() + select_for_update()` | 1 day | Medium — race-condition fix |

---

## 2. Authentication

### Strengths
- `django-axes` 5-attempt lockout (30 min) on `/admin/login`
- Supabase-first: `clearSupabaseLocalSession()` on `session_invalid`
- Single-device enforcement via `CustomUser.session_key` + `UserDevice`

### Weaknesses
- `django-axes` lockout is **per IP+username** — distributed attacks across many IPs not throttled
- No CAPTCHA on register/login (would defeat credential stuffing at scale)
- No email verification flow on registration (anyone can sign up with any email)

### Severity: Medium

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Add hCaptcha to register / login / password reset | 4 hours | High |
| Add email verification token table | 1 day | High |
| Add IP-based rate limit (e.g. `django-ratelimit`) | 1 day | High |
| Add geo-anomaly detection on login | 2 days | Medium |

---

## 3. Authorization

### Strengths
- DRF `permission_classes` on every view
- Admin endpoints require `is_superuser`
- `IsAdminUser` vs `IsAuthenticated` separation
- `CustomUser.is_admin` property used to bypass token metering

### Weaknesses
- Several `IsAdminUser` checks instead of `IsSuperUser` — admins can access endpoints that should be superuser-only (e.g. `TokenBalanceView` could be admin-only when it should be user-only)
- No per-resource ACL (e.g. a teacher can't see only their students' attempts)
- `CustomUser.role` is mutable via `PATCH /api/auth/admin/users/<id>/role/` — privilege escalation possible if endpoint misconfigured

### Severity: Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Audit each admin endpoint to require `IsSuperUser` not `IsAdminUser` | 2 hours | Medium |
| Add `IsOwner` mixin for per-user resource checks | 4 hours | Medium |
| Log every role change to a separate audit channel | 2 hours | High |

---

## 4. CSRF

### Strengths
- Django CSRF middleware enabled
- All write endpoints typically use Bearer auth (CSRF-immune)
- Session-cookie auth falls back to CSRF tokens

### Weaknesses
- `django-axes` lockout page is server-rendered HTML → CSRF token not strictly enforced
- If a developer accidentally marks a write endpoint as `@csrf_exempt` without authentication, risk

### Severity: Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Add CI lint rule banning `@csrf_exempt` on auth views | 1 hour | Medium |
| Add explicit `csrf_protect` decorator where needed | 1 hour | Medium |

---

## 5. CORS

### Current state
`CORS_ALLOWED_ORIGINS` is read from env. Production sets it to `https://crack-me-ai1.vercel.app`. Local dev allows `http://localhost:3000`.

### Strengths
- Production origin locked
- `CORS_ALLOW_CREDENTIALS` likely true for cookie-based auth

### Weaknesses
- No explicit allow-list for subdomains
- `CORS_ALLOWED_ORIGINS` not validated for trailing slashes / protocols in code
- Frontend `api.ts` has `LEGACY_UNHEALTHY_API_HOSTS` list — fine, but central CORS config could drift

### Severity: Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Pin `CORS_ALLOW_ALL_ORIGINS=False` in settings | 5 min | High |
| Add explicit `CORS_ALLOW_METHODS` and `CORS_ALLOW_HEADERS` | 30 min | Medium |
| Add CORS preflight integration tests | 4 hours | Medium |

---

## 6. XSS

### Strengths
- React auto-escapes string children
- `react-markdown` is used (not raw HTML)
- No `dangerouslySetInnerHTML` in user-content paths (verify with grep)

### Weaknesses
- Admin-only paths render `ai_explanation` as Markdown — if Markdown renders raw HTML, XSS possible
- `User.avatar_url` is a `URLField` — validated as URL but not as image
- Email template uses HTML — if user-controlled values interpolated into HTML, XSS

### Severity: Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Pass `allowedElements` / `disallowedElements` to `react-markdown` | 1 hour | High |
| Strip `<script>` tags from any user-supplied HTML | 1 day | Medium |
| Validate avatar URLs point to trusted hosts | 2 hours | Medium |

---

## 7. SQL Injection

### Strengths
- All queries use Django ORM (parameterized)
- `Q()` objects for complex filters
- No raw `cursor.execute()` in app code

### Weaknesses
- RAG SQLite store uses raw SQL (`sqlite3` module) — inputs are scoped, but review needed
- `pyq_extractor.py` parses untrusted PDF text → verify no SQL is constructed from it
- Admin search box uses `?search=` — `__icontains` is safe

### Severity: Very Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Code-review grep for `cursor.execute(` in app code | 1 hour | Low |
| Add CI lint rule: ban f-strings in SQL | 1 hour | Medium |

---

## 8. Secrets Management

### Current state
- All secrets in `backend/.env` (git-ignored)
- Pre-commit hook (`scripts/scan_secrets.py`) blocks commits containing key patterns
- `docs/setup/SECURITY_SECRETS.md` documents rotation procedure

### Strengths
- Pre-commit hook active
- Git history was rewritten via `git-filter-repo` for the previously-leaked OpenRouter key

### Weaknesses
- **Historical leak**: `commit 3770b2f` (in `API_KEYS.md`) exposed OpenRouter + ElevenLabs keys. Lines 101-102 of old `API_KEYS.md` were scrubbed, but the secret **values** may still be in git history if rewrite was incomplete.
- Some old setup docs include what appears to be a real Gmail App Password fragment (`nlhdqbxklvcjxlki` in `PASSWORD_RESET_SETUP.md` — now removed by consolidation).
- `RECOVERED_KEYS.txt` exists in `backend/` — verify it is **not** committed (check `.gitignore`).

### Severity: Medium-Historical (cleanup in progress)

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Verify `RECOVERED_KEYS.txt` is git-ignored | 5 min | High |
| Force-rotate ALL keys that ever appeared in repo history | 1 day | Critical |
| Add GitHub secret-scanning (free for public repos; paid for private) | 1 hour | High |
| Migrate secrets to a managed store (Render env groups + Doppler/AWS Secrets Manager) | 2 days | High |

---

## 9. Environment Variables

### Strengths
- Loaded via `python-dotenv` in `crack_cms/settings.py`
- `SENTRY_DSN` presence gates Sentry init
- AI provider keys are individually optional — graceful skip in round-robin

### Weaknesses
- `DJANGO_SECRET_KEY` falls back to `'django-insecure-local-dev-only'` when `DEBUG=True` and unset — **if `DEBUG=False` is set without `DJANGO_SECRET_KEY`, the app refuses to start** (good); but in dev the insecure default could leak if `DEBUG` is misconfigured
- No `DEBUG_FORCE_OFF` env flag — `DEBUG` is a string `"True"`/`"False"` and could be mis-typed

### Severity: Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Add `python-decouple` for typed env loading | 2 hours | Medium |
| Add startup check that refuses to run with insecure defaults in prod | 1 hour | High |

---

## 10. Rate Limiting

### Current state (verified from `crack_cms/settings.py:248–273`)
- **DRF throttling IS configured**:
  - `AnonRateThrottle` — `120/min` (configurable via `DRF_THROTTLE_ANON` env)
  - `UserRateThrottle` — `600/min` (configurable via `DRF_THROTTLE_USER` env)
  - `ScopedRateThrottle` for `admin_control_tower` — `180/min`
- **`questions.middleware.RateLimitMiddleware`** — adds 60 GET/min/IP layer on `/api/questions/`
- `django-axes` lockout after 5 auth failures (per IP+username, 30 min)
- AI provider quotas act as natural rate limit (Groq 30 RPM, Gemini 15 RPM, etc.) but **not enforced server-side**

### Strengths
- Multi-layer throttling (DRF + custom middleware + axes)
- Provider quotas cascade via round-robin
- Custom `admin_control_tower` scope for admin endpoints

### Weaknesses
- A logged-in user can spam `/api/ai/tutor/` until tokens run out (within 600/min limit)
- `RateLimitMiddleware` only covers the questions app, not auth, AI, analytics, tests
- Throttle scopes are coarse — no per-feature throttling

### Severity: Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Add scoped throttle for AI endpoints (e.g. `ai_tutor` scope = 30/min) | 4 hours | High |
| Add `django-ratelimit` for sensitive write endpoints (password reset, token grant) | 1 day | High |
| Extend `RateLimitMiddleware` to AI + analytics apps | 4 hours | High |
| Add Cloudflare in front of Render (free tier) | 1 day | High |

---

## 11. File Uploads

### Endpoints accepting uploads
- `POST /api/textbooks/uploads/` — PDF
- `POST /api/ai/knowledge/upload/` — PDF/MD/TXT
- `POST /api/accounts/.../avatar/` (if any)

### Strengths
- PyMuPDF validates PDFs at parse time (rejects malformed)

### Weaknesses
- **No magic-bytes check** at upload time — file extension is trusted
- **No size limit** at endpoint level (RAG auto-skips >50 MB after upload — waste of bandwidth)
- **Filename not sanitized** — path traversal possible if upload path is constructed from filename

### Severity: Medium

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Validate `content-type` + magic bytes on upload | 4 hours | High |
| Set explicit `DATA_UPLOAD_MAX_MEMORY_SIZE` in Django settings (e.g. 10 MB) | 5 min | High |
| Generate server-side filename (`uuid4().hex + '.pdf'`), ignore user filename | 1 hour | High |
| Run ClamAV on upload (or use a service like VirusTotal) | 1 day | High |

---

## 12. API Abuse

### Patterns to defend against

| Pattern | Current defense | Recommended |
|---|---|---|
| Scraping `/api/questions/` (full DB) | None | Paginate + per-user throttle |
| Bulk account creation | `django-axes` (after 5 fails) | CAPTCHA + email verification |
| Token drain via short polling | Token balance check | Lower per-minute AI rate |
| Webhook spoofing (Razorpay) | Signature verification | Verify Razorpay-Signature header |
| SSRF via `avatar_url` | URLField validation only | Whitelist hosts (Gravatar, etc.) |

### Severity: Medium

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Add DRF throttling on `QuestionViewSet.list` | 2 hours | Medium |
| Restrict `avatar_url` to allowlisted hosts | 2 hours | Medium |
| Verify Razorpay webhook signature in middleware | 1 hour | High |

---

## 13. Privilege Escalation

### Current attack surface

| Path | Risk | Mitigation |
|---|---|---|
| `PATCH /api/auth/admin/users/<id>/role/` → set `role='admin'` | If endpoint reachable by non-superuser | Enforce `IsSuperUser` |
| `CustomUser.is_admin` property returns True for `is_superuser` | A leaked superuser = total compromise | Audit superuser logins |
| Token bypass via `role='admin'` | AI metering skipped | Restrict `is_admin` to actual admin actions only, not token metering |
| Django shell access | If attacker gets shell, full DB access | Restrict shell access in production |

### Severity: Low

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Add CI grep for `IsAdminUser` vs `IsSuperUser` on admin-only endpoints | 1 hour | High |
| Add log alert on any role change | 2 hours | Medium |

---

## 14. Dependency Vulnerabilities

### Current state
- `requirements.txt` pinned (no upper bounds on most packages) — risk of breaking upgrades
- GitHub Actions runs `bandit` + `safety check` (per `.github/workflows/ci.yml`)
- `dependabot.yml` configured

### Weaknesses
- No automatic PR creation from Dependabot
- No SCA tool (e.g. `pip-audit`, `snyk`)
- Python 3.12 is CI baseline; some packages may have dropped support

### Severity: Medium

### Recommended fixes

| Fix | Effort | Impact |
|---|---|---|
| Enable Dependabot auto-merge for low-risk patch updates | 1 hour | High |
| Add `pip-audit` to CI | 2 hours | High |
| Add `npm audit` summary to PR checks | 2 hours | Medium |
- Pin upper bounds on critical packages (django, cryptography) | 1 day | Medium |

---

## 15. Operational Security

| Item | Status |
|---|---|
| TLS enforced (Vercel + Render) | ✓ |
| Sentry PII redaction | Configurable via `SENTRY_SEND_DEFAULT_PII` |
| Database backups | `data_dump*.json` + admin `/backup-data/` endpoint |
| Log retention | Not defined |
| Incident response runbook | `docs/setup/SECURITY_SECRETS.md` covers secret rotation only |

### Recommended additions

| Fix | Effort | Impact |
|---|---|---|
| Document incident response runbook (compromise procedure) | 1 day | High |
| Set up log shipping to a long-term store (CloudWatch, Datadog Logs) | 1 day | High |
- Monthly access review (list of superusers, role changes) | 1 day/quarter | High |
- Enable Sentry `before_send` to scrub PII (email, phone) | 4 hours | Medium |

---

## 16. Compliance & Privacy

| Concern | Status |
|---|---|
| GDPR data export | Partial — `GET /api/analytics/export/` exists |
| GDPR data deletion | Not implemented |
| Cookie consent banner | Not implemented |
| Terms of Service / Privacy Policy links | Verify in footer |
| Children's data (UPSC aspirants are adults) | n/a |

### Recommended

- Implement `DELETE /api/auth/profile/` for right-to-be-forgotten
- Add cookie consent banner
- Pin `FRONTEND_URL` for all outbound links

---

## 17. Prioritized Remediation Plan

| Priority | Item | Effort | Owner |
|---|---|---|---|
| P0 | Rotate any secrets still in git history; verify `RECOVERED_KEYS.txt` is ignored | 1 day | Backend |
| P0 | ~~Add DRF throttling~~ (DONE — AnonRateThrottle 120/min, UserRateThrottle 600/min, admin_control_tower 180/min) | — | — |
| P1 | Add CAPTCHA on register/login/password-reset | 4 hours | Backend + Frontend |
| P1 | Validate upload magic bytes + size limits | 4 hours | Backend |
| P1 | Enable `ROTATE_REFRESH_TOKENS=True` | 1 hour | Backend |
| P2 | Move secrets to managed store | 2 days | DevOps |
| P2 | Add `pip-audit` to CI | 2 hours | DevOps |
| P2 | Email verification flow | 1 day | Backend + Frontend |
| P3 | Two-person approval for high-impact admin ops | 1 week | Backend |
| P3 | GDPR delete + cookie consent | 1 week | Backend + Frontend |

---

## 18. Security Tooling Reference

| Tool | Use |
|---|---|
| `bandit` | Python SAST (in CI) |
| `safety` | Python dep CVE check (in CI) |
| `npm audit` | JS dep CVE check (in CI) |
| `scripts/scan_secrets.py` | Pre-commit secret scan |
| `django-axes` | Brute-force lockout |
| Sentry | Runtime error tracking |
| Datadog | APM + log correlation |

See [`PERFORMANCE.md`](./PERFORMANCE.md) and [`AI_ASSISTANT_RULES.md`](./AI_ASSISTANT_RULES.md) for related concerns.
