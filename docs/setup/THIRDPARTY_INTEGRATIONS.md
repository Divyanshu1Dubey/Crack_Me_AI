# Third-Party Integrations Setup

> Single-source checklist for every external service CrackCMS uses.
> Status legend — ✅ Already wired in code · 🟡 Code complete, needs creds · ⚠️ Not yet wired.

---

## At a Glance

| Service | Purpose | Status | Code Locations | Env Var |
|---|---|---|---|---|
| **Supabase** | Auth + Postgres | ✅ | `accounts/supabase_*`, `frontend/src/lib/supabase.ts` | `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL` |
| **Razorpay** | Payments | ✅ | `accounts/views.py` (Subscribe), `subscription/page.tsx` | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` |
| **GMAIL SMTP** | Transactional email | ✅ | `crack_cms/settings.py` | `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` |
| **Google Analytics (GA4)** | Marketing analytics | ✅ | `frontend/src/app/layout.tsx`, `lib/analytics.ts` | `NEXT_PUBLIC_GA_MEASUREMENT_ID` |
| **Microsoft Clarity** | Session recordings | 🟡 | `frontend/src/components/ClarityInit.tsx` | `NEXT_PUBLIC_CLARITY_ID` |
| **PostHog** | Product analytics | 🟡 | `frontend/src/components/PostHogInit.tsx` | `NEXT_PUBLIC_POSTHOG_KEY` |
| **Datadog** | Backend APM + RUM | ✅ | `crack_cms/settings.py`, `components/DatadogInit.tsx` | `DD_API_KEY`, `DD_SERVICE` |
| **Sentry** | Error tracking | ✅ | `crack_cms/settings.py` | `SENTRY_DSN` |
| **Giscus** | Blog comments | 🟡 | `frontend/src/components/CommentsGiscus.tsx` | (inline constants) |
| **AI Providers (×11)** | Inference round-robin | ✅ | `ai_engine/services.py` | Per-provider keys, see `AI_PROVIDERS.md` |
| **Redis (optional)** | Cache | ✅ | `crack_cms/settings.py` | `REDIS_URL` |
| **Render** | Backend hosting | ✅ | `render.yaml`, `build.sh` | (Render dashboard) |
| **Vercel** | Frontend hosting | ✅ | `frontend/vercel.json` | (Vercel dashboard) |

---

## 1. Razorpay (Payments) — Set this up FIRST because revenue blocker

**Why:** Used by `/subscription/` to accept plans (₹129 / ₹449 / ₹1999 / ₹79 scholarship).

### Step-by-step
1. Sign up at [razorpay.com](https://razorpay.com) (use business email).
2. KYC: PAN, bank account, business proof (~24 h to activate live mode).
3. Switch account to **Live Mode** (top-left toggle).
4. Generate API keys: **Settings → API Keys → Generate Live Key**.
   - Copy `key_id` (starts with `rzp_live_`)
   - Copy `key_secret` (⚠️ shown once — save immediately)
5. **Webhook secret**: **Settings → Webhooks → Add New Webhook**
   - URL: `https://crackcms-vsthc.ondigitalocean.app/api/auth/subscribe/webhook/`
   - Active events: `payment.captured`, `payment.failed`, `order.paid`
   - Copy the **Signing Secret** (this is `RAZORPAY_WEBHOOK_SECRET`).
6. Set on **Render dashboard → Backend Service → Environment**:
   ```
   RAZORPAY_KEY_ID = rzp_live_XXXXXXXX
   RAZORPAY_KEY_SECRET = XXXXXXXXXX
   RAZORPAY_WEBHOOK_SECRET = XXXXXXXXXX
   ```
7. Set on **Vercel dashboard → Frontend Project → Environment Variables** (all envs):
   ```
   NEXT_PUBLIC_RAZORPAY_KEY_ID = rzp_live_XXXXXXXX
   ```

### Verify
1. Trigger ₹1 test plan via `/subscription/`.
2. Confirm: order created in Razorpay Dashboard → Payments, sub activated in DB, 2 confirmation emails sent.
3. Check webhook in Razorpay Dashboard → Webhooks → Logs (should be 200 OK).

---

## 2. Supabase (Auth + Postgres)

**Status:** Already wired. See [`setup/SUPABASE_SETUP.md`](./SUPABASE_SETUP.md) for full migration runbook.

### Required env (Render + Vercel)
```
# Backend
SUPABASE_URL = https://xxxxx.supabase.co
SUPABASE_KEY = service_role key (NOT anon)
SUPABASE_DATABASE_URL = postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres
# Frontend
NEXT_PUBLIC_SUPABASE_URL = https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = sb_publishable_xxxxx
# or, for legacy code paths:
NEXT_PUBLIC_SUPABASE_ANON_KEY = eyJhbGciOi...
```

---

## 3. Google Analytics 4 (GA4) — Already partially configured

**Default in `layout.tsx`:** `G-MM88RT1QQK` (CrackLabs property).

### Optional: create your own GA4 property
1. Go to [analytics.google.com](https://analytics.google.com) → Admin → Create Property.
2. Choose **GA4**, name it (e.g. "cracklabs.app"), set timezone, currency.
3. Data Streams → Add → Web → URL `https://www.cracklabs.app` → copy **Measurement ID** (`G-XXXXXXXX`).
4. Replace `NEXT_PUBLIC_GA_MEASUREMENT_ID` on Vercel.
5. Submit sitemap: GA4 Admin → Data Streams → Web → Sitemap → add `https://www.cracklabs.app/sitemap.xml`.

### Events to track (already wired)
- `page_view` (auto)
- `sign_up`
- `login`
- `question_viewed`
- `ai_tutor_query`
- `subscription_started`
- `subscription_completed`
- `subscription_payment_failed`
- `download_resource`

---

## 4. Microsoft Clarity (Session recordings + heatmaps)

1. Sign up at [clarity.microsoft.com](https://clarity.microsoft.com) → New Project.
2. Copy **Project ID** from the install snippet.
3. Set `NEXT_PUBLIC_CLARITY_ID = XXXXXXX` on Vercel.
4. The `ClarityInit` component picks it up automatically.

### Verify
- Reload a page on production, wait 2 minutes → Recordings → New sessions appear.

---

## 5. PostHog (Product analytics)

1. Sign up at [posthog.com](https://posthog.com) (cloud or self-host).
2. Project Settings → Project → copy **Project API Key** and **Host** (`https://us.i.posthog.com` or `https://eu.i.posthog.com`).
3. Set on Vercel:
   ```
   NEXT_PUBLIC_POSTHOG_KEY = phc_xxxxx
   NEXT_PUBLIC_POSTHOG_HOST = https://us.i.posthog.com
   ```
4. The `PostHogInit` component initializes automatically on first page load.

### Verify
- PostHog Activity → Live Events → see `pageview`, `$identify`, custom events.

---

## 6. Datadog (Backend APM + Frontend RUM)

### Backend (Render)
1. Org at [datadoghq.com](https://datadoghq.com) → Org Settings → API Keys → New Key.
2. Set on Render:
   ```
   DD_API_KEY = xxxxxxxxxx
   DD_SERVICE = crackcms-backend
   DD_ENV = production
   DD_VERSION = <release-sha>
   DD_SITE = datadoghq.com
   ```
3. `crack_cms/settings.py` already imports `ddtrace` via `requirements.txt`.
4. Set `DD_LOGS_INJECTION=true` to correlate logs.

### Frontend (Vercel)
1. Datadog → RUM → New Application → Browser → copy **Application ID** and **Client Token**.
2. Set on Vercel:
   ```
   NEXT_PUBLIC_DD_APPLICATION_ID = xxxxxx-xxxx-xxxx
   NEXT_PUBLIC_DD_CLIENT_TOKEN = pub_xxxxx
   NEXT_PUBLIC_DD_SITE = datadoghq.com
   ```
3. `DatadogInit` initializes on first render.

### Verify
- APM → Services → `crackcms-backend` should appear within 5 min.
- RUM → Applications → browser sessions should land within 1 min of page load.

---

## 7. Sentry (Error tracking)

1. Sign up at [sentry.io](https://sentry.io) → New Project → Python (Django).
2. Copy **DSN** from **Project Settings → Client Keys (DSN)**.
3. Set on Render:
   ```
   SENTRY_DSN = https://xxxxxxx@xxxxxxx.ingest.sentry.io/xxxxxxx
   SENTRY_TRACES_SAMPLE_RATE = 0.1       # 10% in prod (1.0 in dev)
   SENTRY_SEND_DEFAULT_PII = false       # never in prod
   ```
4. `crack_cms/settings.py` initializes sentry when DSN is set.

### Verify
- Trigger a 500 in admin (e.g. malformed payload), wait 1 min → Sentry Issues → new error appears.

---

## 8. Giscus (Blog comments)

1. Make sure GitHub Discussions is enabled on your repo (Settings → General → Features).
2. Install the [giscus GitHub app](https://github.com/apps/giscus) on your repo (only the repo, not org-wide).
3. In your repo, create a **Discussion category** called `Comments` (Discussions → New Category).
4. Visit [giscus.app](https://giscus.app/) → fill in:
   - **Repository:** `Divyanshu-Dubey/crack_cms`
   - **Discussion category:** `Comments`
   - **Mapping:** `Pathname`
   - **Theme:** `light` and `dark`
   - **Reactions:** enabled
5. Copy the five env values from the generated script:
   ```
   data-repo="Divyanshu-Dubey/crack_cms"
   data-repo-id="R_kgDOXXXX"     # ← repo id
   data-category="Comments"
   data-category-id="DIC_kwDOXXXX"  # ← category id
   data-theme="light"
   ```
6. Edit `frontend/src/components/CommentsGiscus.tsx`:
   - Replace the placeholder `repo`, `repoId`, `category`, `categoryId`, `theme` props with the values from step 5.
7. (Alternative) wire to env vars: `NEXT_PUBLIC_GISCUS_REPO`, `NEXT_PUBLIC_GISCUS_REPO_ID`, `NEXT_PUBLIC_GISCUS_CATEGORY`, `NEXT_PUBLIC_GISCUS_CATEGORY_ID`, `NEXT_PUBLIC_GISCUS_THEME`.

### Verify
- Open `https://www.cracklabs.app/blog/<post-slug>`, scroll to bottom — comment box renders.
- Post a comment → check GitHub Discussions → category `Comments` → new thread.

---

## 9. AI Provider Keys (11 providers)

See [`setup/AI_PROVIDERS.md`](./AI_PROVIDERS.md) for provider-specific guides.
Quick verify: `python test_api_keys.py` runs the suite and reports per-provider status.

Required env (Render):
```
GROQ_API_KEY              # provider 1
CEREBRAS_API_KEY          # provider 2
GEMINI_API_KEY            # provider 3 (×2 models)
COHERE_API_KEY            # provider 4
OPENROUTER_API_KEY        # provider 5
OPENROUTER_API_KEY2       # provider 6
GITHUB_TOKEN              # provider 7 (GitHub Models)
HUGGINGFACE_API_KEY       # provider 8
MISTRAL_API_KEY           # provider 9
NVIDIA_MISTRAL_API_KEY    # provider 10
DEEPSEEK_API_KEY          # provider 11 (paid, last in rotation)
```
Missing keys = silently skipped; round-robin continues.

---

## 10. Gmail SMTP (transactional email)

See [`setup/EMAIL_SETUP.md`](./EMAIL_SETUP.md).

Required env:
```
EMAIL_HOST_USER = crackwith.ai@gmail.com
EMAIL_HOST_PASSWORD = xxxx xxxx xxxx xxxx   # Google App Password (NOT regular password)
```

Generate App Password: Google Account → Security → 2-Step Verification → App passwords → name "CrackCMS" → copy.

---

## 11. Redis (Optional — falls back to in-memory cache)

Only required if you want cross-process cache sharing.

```
REDIS_URL = rediss://default:xxx@xxx.upstash.io:6379   # Upstash
# or
REDIS_URL = redis://:xxx@xxx.render.com:6379           # Render Redis
```

When invalid or absent → settings.py falls back to `LocMemCache` automatically.

---

## Verification Checklist

Run after all credentials are set:

```bash
# Backend
cd backend
python manage.py check --deploy
python test_api_keys.py          # all 11 AI providers ✓
python -c "from django.core.mail import send_mail; send_mail('Test', 'OK', None, ['you@example.com'])"
python manage.py shell -c "from accounts.models import Subscription; print(Subscription.objects.count())"

# Frontend (Vercel preview deployment)
curl -I https://cracklabs.app/api/health/        # 200
curl -I https://cracklabs.app/auth/profile/     # 401 (correct, auth required)
```

Then in browser:
- [ ] Open homepage → DevTools Network → see requests to `googletagmanager.com`, `clarity.ms`, `posthog.com`, browser-intake-datadoghq.com.
- [ ] Subscribe to ₹129 plan → Razorpay checkout → DB row created → 2 emails received.
- [ ] Post a blog comment → appears in GitHub Discussions.
- [ ] Trigger a 500 → Sentry issue lands within 1 minute.
- [ ] Datadog APM → service appears with traffic + traces.

---

## See Also
- [`SUPABASE_SETUP.md`](./SUPABASE_SETUP.md) — Supabase + Postgres migration
- [`DATADOG_SETUP.md`](./DATADOG_SETUP.md) — Env vars reference
- [`EMAIL_SETUP.md`](./EMAIL_SETUP.md) — Gmail App Password
- [`AI_PROVIDERS.md`](./AI_PROVIDERS.md) — 11 AI providers + Ollama fallback
- [`../reference/SECURITY_SECRETS.md`](../reference/SECURITY_SECRETS.md) — Secret rotation policy
