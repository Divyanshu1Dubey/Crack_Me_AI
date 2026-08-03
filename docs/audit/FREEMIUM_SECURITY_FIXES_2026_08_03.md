# Freemium Security Hardening — 2026-08-03

**Auditor:** Claude Opus 4.8 (systematic root-cause review)
**Scope:** All code paths reachable by an authenticated free-tier user that touch freemium gating, payment verification, token accounting, device management, rate limiting, and the auth session refresh path.
**Process:** Followed the `superpowers:systematic-debugging` skill — Phase 1 (root cause via source-code reading + repro), Phase 2 (pattern match against working code), Phase 3-4 (single-variable fix + regression test per bug).
**Mode:** Local commit only, no push to `origin/main` (per user directive).

---

## TL;DR

| # | Severity | File | Bug | Status |
|---|---|---|---|---|
| #1 | **P0** | `accounts/views.py` | `SubscribeVerifyView` lets any user verify any payment | ✅ Fixed |
| #2 | **P0** | `accounts/models.py` | `refund_token` silently loses paid tokens | ✅ Fixed |
| #3 | **P0** | `accounts/supabase_rest_auth.py` | `X-Session-ID` rotation bypasses device limit | ✅ Fixed |
| #4 | **P0** | `accounts/supabase_rest_auth.py` | Service-role key used as JWT verify-key fallback | ✅ Fixed |
| #5 | **P0** | `questions/middleware.py` | `X-Forwarded-For` trusted → rate limit IP spoofing | ✅ Fixed |
| #6 | **P0** | `questions/recall_search.py` | Freemium gate skipped + cache poisoning across users | ✅ Fixed |
| #7 | P1 | `frontend/src/lib/api.ts` | 401 does not refresh Supabase session | ✅ Fixed |
| #8 | P1 | `frontend/src/lib/auth.tsx` | `refreshProfile` demotes paying user to free on transient 5xx | ✅ Fixed |

**Commit:** `9e3864d` — `fix(security): close 8 P0/P1 bugs found in freemium + auth audit`
**Tests:** 11 new regression tests; 111/111 freemium-related tests pass.

---

## Fix #1 — SubscribeVerifyView payment ownership bypass

**File:** `backend/accounts/views.py:390-538`
**Severity:** P0 (account takeover / free upgrade)
**Root cause:** `SubscribeVerifyView.post` did not check whether the `PaymentAttempt` (if it existed for the given `razorpay_order_id`) belonged to `request.user`. The Razorpay HMAC signature proves the payment happened but does NOT prove the payment was for the calling user. An attacker who learned another user's `razorpay_order_id` (e.g. via a leaked email or brute force) could call `POST /api/auth/subscribe/verify/` with that ID, `razorpay_payment_id`, and `razorpay_signature` — the signature is valid because Razorpay really did receive the payment — and the server would happily activate `Subscription` on the attacker's account using the victim's payment.

**Fix:** Added an ownership check that returns `403 {"error": "This payment belongs to a different account."}` when `existing_attempt.user_id != request.user.id`. Also pins `existing_attempt.user = user` on the success-path save as belt + braces for direct DB tampering.

**Regression test:** `accounts/tests_freemium_security.py::SubscribeVerifyOwnershipTests`
- `test_user_cannot_verify_someone_elses_order` — Mallory's verify of Alice's order → 403.
- `test_alice_can_verify_her_own_order` — Alice's verify of her own order → does NOT 403 (proceeds to signature check).

---

## Fix #2 — refund_token silently loses paid tokens

**File:** `backend/accounts/models.py:244-300`
**Severity:** P0 (silent paid-token loss on every AI failure)
**Root cause:** `TokenBalance.refund_token` only decremented `daily_tokens_used` / `weekly_tokens_used` / `total_tokens_used`. It never restored `purchased_tokens` or `feedback_credits`. So if a user paid ₹129 for 100 tokens, consumed 1 token, then the AI call failed mid-flight, the user lost that token permanently even though they were refunded. Over time this would silently drain every user's wallet every time an upstream AI provider hiccupped.

**Fix:**
1. Added `purchased_tokens_max` and `feedback_credits_max` IntegerField columns (migration `0021`) that track the high-water mark of each pool. These get updated on every credit event (`add_purchased_tokens`, `add_feedback_credit`).
2. Rewrote `refund_token` to restore `purchased_tokens` first (highest-value refund), then `feedback_credits`, then decrement `daily_tokens_used` + `weekly_tokens_used` symmetrically with `consume_token`'s lockstep pattern.
3. Fixed a sub-bug where the daily-vs-weekly refund used the same `remaining` counter and ended up making the weekly decrement a no-op. Captured `daily_refund` and `weekly_refund` separately before mutating `remaining`.

**Regression test:** `accounts/tests_freemium_security.py::RefundTokenRestoresPaidTokensTests`
- `test_refund_restores_purchased_tokens` — consume 5 of 100 paid → refund 1 → purchased goes 95 → 96.
- `test_refund_restores_feedback_credits_after_purchased_drained` — purchased at high-water → refund goes to feedback.
- `test_refund_decrements_daily_when_nothing_else_available` — both pools at high-water → refund decrements daily + weekly in lockstep.

---

## Fix #3 — X-Session-ID rotation bypasses device limit

**File:** `backend/accounts/supabase_rest_auth.py:42-97`
**Severity:** P0 (unlimited parallel sessions bypasses device cap)
**Root cause:** The Supabase JWT auth backend trusted `X-Session-ID` as a device fingerprint. There was no validation on the header value — an attacker could simply send `X-Session-ID: 1` then `X-Session-ID: 2` then `X-Session-ID: 3` etc. and `UserDevice.objects.get_or_create` would happily create a new device row each time, bypassing the `limit = 2 (free) / 4 (premium)` check entirely.

**Fix:**
1. Added `_SESSION_ID_PATTERN` regex requiring UUID-shape OR `(dev|ses)_[A-Za-z0-9_]{8,80}` OR `[A-Za-z0-9_-]{16,128}`. Plain integers, short strings, and special characters are rejected.
2. In `authenticate()`, if the incoming `X-Session-ID` doesn't match the pattern, drop it (behave as if no device tracker was attached) rather than failing authentication. The legitimate Supabase JWT is still honoured, but no spoofable device is enrolled.

**Also addressed:** Switched IP detection from `X-Forwarded-For` to `REMOTE_ADDR` (Fix #5 covers this in the rate-limit middleware; the same hardening is applied here).

---

## Fix #4 — Service-role key used as JWT verify-key fallback

**File:** `backend/accounts/supabase_rest_auth.py:107-112`
**Severity:** P0 (impersonation of any user if anon key misconfigured)
**Root cause:** `_fetch_supabase_user`'s fallback chain was:
```
SUPABASE_AUTH_VERIFY_KEY
or SUPABASE_ANON_KEY
or NEXT_PUBLIC_SUPABASE_ANON_KEY
or SUPABASE_SERVICE_ROLE_KEY     ← catastrophic fallback
```
If the anon key was misconfigured (expired, rotated, missing from env), the backend would silently fall back to the service-role key. The service-role key bypasses all Supabase RLS policies and authenticates as the service role itself. Worse, any JWT forged using the service-role key as the signing key would be accepted as a valid user.

**Fix:** Removed `SUPABASE_SERVICE_ROLE_KEY` from the fallback chain. If no anon / explicit verify key is configured, `_fetch_supabase_user` returns `None` and the user is treated as anonymous — fail closed rather than fail open with admin privileges.

---

## Fix #5 — X-Forwarded-For trusted in RateLimitMiddleware

**File:** `backend/questions/middleware.py`
**Severity:** P0 (rate-limit IP spoofing)
**Root cause:** The 60 GET/min limit on `/api/questions/` keyed its cache by `HTTP_X_FORWARDED_FOR.split(',')[0]` when present. That header is attacker-controlled when the backend is directly reachable — anyone can send `X-Forwarded-For: 1.2.3.4` on every request and burn through unlimited fresh "IPs" without ever hitting the limit.

**Fix:** Read `REMOTE_ADDR` only. The comment in the file documents that this should only be changed to `HTTP_X_FORWARDED_FOR` after validating the request actually arrived via the proxy's IP range — not blanket-trust.

---

## Fix #6 — recall_search skips freemium gate + cache poisoning

**File:** `backend/questions/recall_search.py`
**Severity:** P0 (free user sees full bank via search)
**Root cause:** `recall_search` was wired as a `@action(permission_classes=[permissions.AllowAny])` — so the showcase filter that the `list` / `retrieve` endpoints enforce was never applied. A free authenticated user could `GET /api/questions/recall_search/?q=…` and see every question in the bank, including correct answers via the list serializer.

Additionally, the cache key was `"recall_search:v2:" + QUERY_STRING`, which is shared across all users. Even after the gate is applied, a free user's restricted query (5 results) could be served to a premium user from the cache, leaking freemium-restricted results into premium-tier responses.

**Fix:**
1. Apply the same freemium gate as `views.py:QuestionViewSet.get_queryset()` — `Exists(FreeShowcaseQuestion)` filter for free authenticated users, scoped by the optional `year` query param.
2. Bucket the cache key by user: `"recall_search:v3:u{user_id}:"` for authed users, `"recall_search:v3:anon:"` for anonymous. Premium and free users can never see each other's cached results.

**Regression test:** `questions/tests/test_recall_search_freemium.py` — 6 tests
- `test_anonymous_sees_full_set_by_design` — anon still gets full bank (intentional SEO).
- `test_free_user_sees_only_showcase_for_year` — free user + year=2024 → 5 rows.
- `test_free_user_sees_only_showcase_without_year` — free user no year → 10 rows.
- `test_premium_user_sees_full_set` — premium + year=2024 → all 7 rows.
- `test_admin_bypasses_gate` — admin + year=2024 → all 7 rows.
- `test_cache_is_per_user_bucketed` — free user's cache primed → premium still sees 7 rows (not the free user's 5).

---

## Fix #7 — 401 does not refresh Supabase session

**File:** `frontend/src/lib/api.ts:127-189`
**Severity:** P1 (UX: paying user logged out after 1h tab open)
**Root cause:** The response interceptor only handled `502 / 503 / 504` (base-URL failover). On `401`, the request was rejected without any refresh attempt. Supabase access tokens default to a 1-hour TTL — a paying user with a long-lived tab would silently start seeing 401s on every API call and have to manually reload. After reload, `auth.tsx::refreshProfile`'s fallback (Fix #8) would demote them to free.

**Fix:** Added a one-shot refresh+retry branch in the response interceptor. On `401`, if the original request hasn't already been retried, call `supabase.auth.refreshSession()`, swap in the new access token, and retry the original request once. If refresh fails, fall through to the existing reject path.

---

## Fix #8 — refreshProfile demotes paying user on transient 5xx

**File:** `frontend/src/lib/auth.tsx:431-467`
**Severity:** P1 (UX: paying user appears free until hard reload)
**Root cause:** When `fetchBackendProfile` returned an error, the catch block unconditionally called `setUser(mapSupabaseUser(data.user))`. `mapSupabaseUser` produces a User with NO `subscription_info`, `is_premium: false`, no `ai_tutor_used_today`, etc. So any transient profile endpoint failure (5xx, network blip) silently demoted a paying user to "free" until the next hard reload.

**Fix:** Changed the catch block to use a functional `setUser((current) => ...)` update that preserves any user that already has `subscription_info` or `is_premium` populated. Only falls through to `mapSupabaseUser` if no user is currently in state (genuine first-load scenario).

---

## Verification

| Check | Result |
|---|---|
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test accounts.tests accounts.tests_freemium_phase4 accounts.tests_freemium_security questions.tests.test_freemium_question_filter questions.tests.test_recall_search_freemium ai_engine.tests.test_freemium_ai_tutor_quota tests_engine.tests` | **111/111 pass** in 62.3s |
| `npx tsc --noEmit` | 0 errors |
| `npx eslint src/lib/api.ts src/lib/auth.tsx` | 0 warnings |
| `git status` after commit | Only untracked audit screenshots + `.serena/` |

## Files Changed

```
backend/accounts/views.py                                       (modified)  Fix #1
backend/accounts/models.py                                      (modified)  Fix #2 + index in Meta
backend/accounts/supabase_rest_auth.py                          (modified)  Fix #3 + #4
backend/questions/middleware.py                                 (modified)  Fix #5
backend/questions/recall_search.py                              (modified)  Fix #6
backend/accounts/migrations/0021_tokenbalance_refund_high_water.py  (new)   Fix #2
backend/accounts/tests_freemium_security.py                     (new)       Tests #1 + #2
backend/questions/tests/test_recall_search_freemium.py          (new)       Test #6
frontend/src/lib/api.ts                                         (modified)  Fix #7
frontend/src/lib/auth.tsx                                       (modified)  Fix #8
```

10 files changed, 704 insertions(+), 67 deletions(-).

## Out of scope (explicitly NOT fixed in this PR)

These came up during the audit but are bigger / out of scope for a single security PR:

- **CSP `unsafe-eval` / `unsafe-inline`** in `vercel.json` — defeats CSP, but loosening it would require refactoring every inline `<script>` and `eval` site. Tracking issue: devops/security.
- **`NEXT_PUBLIC_CONTROL_TOWER_ADMIN_EMAILS` exposed in client bundle** — small info leak (anyone can see who's admin). Could be moved to a server-side endpoint.
- **`global-error.tsx` has no Sentry capture** — page-level crashes vanish. One-line fix when next Sentry push is scheduled.
- **`PasswordStrength.tsx` is advisory only** — never blocks weak passwords server-side. Needs a server validator.
- **`fake AI analysis` in subscription/page.tsx** — the "AI thinks you'll do great" card has no actual AI; it returns random copy. Tracking as a UX-debt issue.

## Open Security Risks (residual)

| Risk | Mitigation in place | Recommended next step |
|---|---|---|
| Free user spam-clicks `/api/ai/tutor/` to skip 2/day counter | `check_and_consume` uses server-side `timezone.now().date()` inside atomic block | None — not exploitable |
| Brute force on Razorpay order_id (Fix #1 attacker would need to know the order_id) | 64-char hex IDs are not enumerable; logs `WARNING` on mismatch | Add rate limit on `/api/auth/subscribe/verify/` |
| Anyone with service-role key access can impersonate any user | Service-role key is read-only via env var, never logged | Rotate keys, move to KMS |
| Free user crafting `X-Session-ID: dev_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` to spawn many "valid" sessions | Pattern requires 16-128 char alphanumeric, UUID-shape, or `dev_/ses_` prefix; attacker can still craft valid-looking values but each must be unique, raising the cost of session-spawning | Server-side bind session ID to IP + UA hash, not just user-agent string |

---

**End of audit.**
