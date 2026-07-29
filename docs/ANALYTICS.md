# Analytics & Tracking

> **Single source of truth** for the production analytics stack — vendor
> choices, event taxonomy, consent model, UTM persistence, the internal
> admin dashboard, verification steps, and the dashboards that exist on
> each vendor.
>
> Shipped in commit `57f4dfb` — `feat(analytics): enterprise-grade
> product analytics, SEO tracking and conversion funnels`.

---

## 1. Goals

The analytics stack is built to answer five questions:

1. **Where do users come from?** — campaign attribution + UTM persistence.
2. **What do they do?** — page views, scroll depth, engagement, feature
   adoption, conversion funnels.
3. **Why do they leave (or stay)?** — Clarity heatmaps/recordings,
   PostHog retention cohorts, GA4 engagement.
4. **What is the AI doing?** — AI tutor opens, conversations, messages,
   feedback, RAG hits, top topics.
5. **Where is the money?** — pricing views, checkout starts, payments,
   coupons, revenue, MRR.

Every page, every CTA, every conversion event is captured without firing
duplicate pageviews. Existing GA4 wiring was preserved and improved
rather than replaced.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Frontend (Next.js)                            │
│                                                                     │
│  ┌──────────────┐  ┌─────────────────┐  ┌──────────────────────┐   │
│  │ GA4 (gtag.js)│  │ Microsoft       │  │ PostHog (snippet)    │   │
│  │ inline in    │  │ Clarity         │  │ consent-gated        │   │
│  │ layout       │  │ consent-gated   │  │ autocapture + pagev  │   │
│  └──────┬───────┘  └────────┬────────┘  └──────────┬───────────┘   │
│         │                   │                       │               │
│         └────────┬──────────┴───────────────────────┘               │
│                  │  analytics.event()  (single typed surface)       │
│                  ▼                                                  │
│         ┌────────────────────────┐    ┌─────────────────────────┐  │
│         │ Datadog RUM            │    │ Internal backend relay  │  │
│         │ (already wired)        │    │ POST /api/analytics/     │  │
│         │ safeDdAction()         │    │ events/  (debounced)    │  │
│         └────────────────────────┘    └────────────┬────────────┘  │
│                                                    │               │
│  ConsentBanner.tsx ───► consent.onChange() ──► vendor opt-in/out  │
│  pageClassifier.ts ───► stable page_type/page_group on every PV    │
│  attribution.ts ─────► localStorage UTM, 30-day TTL                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Backend (Django + DRF)                           │
│                                                                     │
│  AnalyticsIngestView (AllowAny, throttle_scope='analytics_ingest') │
│       │                                                             │
│       ▼                                                             │
│  AnalyticsEvent (append-only)                                       │
│     id, event_name, visitor_id, session_id, user_id                 │
│     path, page_type, page_group, utm_*, device, browser, os, country│
│     properties (JSONField, 8 KB cap), created_at                    │
│                                                                     │
│  AnalyticsDashboardDataView (IsAdminUser) — pre-aggregated          │
│     realtime (5-min active), today/weekly/monthly KPIs              │
│     top pages, top blogs, top searches, top countries               │
│     devices, browsers, campaigns, conversion funnel                │
│     30-day daily-active chart                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 Vendor fan-out

`frontend/src/lib/analytics.ts` is the single typed surface. Every event
flows through `analytics.event(name, params)` which:

1. **Deduplicates** page_view by `lastPagePath`.
2. **Enriches** with `page_type`/`page_group` from `pageClassifier.ts`.
3. **Attaches** persisted UTM (localStorage `crackcms_attribution_v1`,
   30-day TTL).
4. **Fans out** to GA4 (`safeGtag`), Clarity (`safeClarity`), PostHog
   (`safePosthog`), Datadog (`safeDdAction`) — all vendor helpers
   no-op on SSR / missing vendor.
5. **Relays** a debounced subset of high-value conversion events to the
   internal backend (`maybeRelay`, 50 ms) so we own a row in our own
   DB regardless of third-party outages.

### 2.2 Consent model

Three categories, stored in `localStorage.crackcms_consent_v1`:

| Category    | Includes                           | Default |
|-------------|------------------------------------|---------|
| `essential` | Auth, session, security            | always  |
| `analytics` | GA4, PostHog, internal relay       | off     |
| `marketing` | Clarity heatmaps, ad pixels        | off     |

`ConsentBanner.tsx` renders on first visit; user choice is persisted.
`consent.onChange(cb)` lets vendor loaders (`ClarityInit`,
`PostHogInit`) flip on/off at runtime via
`gtag('consent', 'update')` and PostHog `opt_in_capturing` /
`opt_out_capturing`. Scripts are **never** loaded until consent is
granted (we render the `<Script>` only after the corresponding flag is
true).

### 2.3 Identity & session

| Key                       | Lifetime       | Source                                  |
|---------------------------|----------------|-----------------------------------------|
| `crackcms_visitor_v1`     | localStorage   | `crypto.randomUUID()` on first visit    |
| `crackcms_session_v1`     | sessionStorage | `crypto.randomUUID()` per browser tab  |
| `crackcms_attribution_v1` | localStorage   | UTM bundle, 30-day TTL                  |

`analytics.identity(id)` propagates `user_id` to GA4 (gtag `set`) and
PostHog (`posthog.identify`). `analytics.session.start()` fires
`session_start` (and `return_visit` if the visitor has been here in the
last 30 days), plus a 15-second `engagement_time` heartbeat.

### 2.4 Page classification

`pageClassifier.ts` maps every existing route to a stable
`page_type`/`page_group` so dashboards never fragment across renames.
The classifier understands ~60 routes including:

- `/`, `/blog`, `/blog/[slug]`, `/blog/category/[category]`
- `/cms/pyq/[year]`, `/cms/subject/[slug]`, `/cms/topic/[slug]`
- `/exams/[slug]`, `/exams/[slug]/[guideSlug]`,
  `/exams/[slug]/[comparisonSlug]`
- `/neet-pg`, `/neet-pg/vs-usmle`, `/inicet`
- `/dashboard`, `/questions/practice`, `/questions/flashcards`,
  `/questions/bookmarks`, `/questions/notes`
- `/ai-tutor`, `/study-planner`, `/leaderboard`,
  `/subscription`, `/pricing`, `/profile`
- `/search`, `/login`, `/register`, `/auth/*`
- `/admin/*` (sub-tree), `/mock-test/*`, `/mock-test/[id]/result`

The classifier is the only place that touches path strings — adding a
new route means one entry here.

---

## 3. Event Taxonomy

Defined as a TypeScript union in `frontend/src/lib/analytics.ts:54`.
~50 named events across five categories. Type-safe fan-out to all
vendors — `analytics.event()` rejects unknown names at compile time.

### 3.1 Navigation & engagement

| Event             | When                                            | Properties |
|-------------------|-------------------------------------------------|------------|
| `page_view`       | First mount of every route (deduped)            | `page_type`, `page_group`, `path`, `referrer` |
| `session_start`   | First user-visible interaction                  | `is_returning` |
| `engagement_time` | Every 15 s while tab is visible                 | `seconds` |
| `scroll_depth`    | Buckets 25/50/75/100 (per-page high-watermark)  | `percent`, `page_type` |
| `exit_intent`     | Tab hidden (visibilitychange)                   | `seconds_on_page` |
| `return_visit`    | New session within 30 days of last session      | `days_since_last` |
| `outbound_click`  | Click on a different-origin link                | `url`, `host` |
| `search_query`    | Site search submit                              | `query`, `results_count` |
| `search_result_click` | Click on a search result                    | `query`, `position` |
| `error`           | Global JS error (filtered: no favicon noise)    | `message`, `source`, `line` |

### 3.2 Consent & identity

| Event           | When                              | Properties |
|-----------------|-----------------------------------|------------|
| `consent_update`| User updates consent preferences  | `essential`, `analytics`, `marketing` |
| `sign_up`       | Successful registration           | `method`, `referral_source` |
| `login`         | Successful login                  | `method`, `is_supabase` |

### 3.3 Blog (per-post overlay via `BlogAnalytics.tsx`)

| Event                  | When                                                 | Properties |
|------------------------|------------------------------------------------------|------------|
| `blog_view`            | Mount of any `/blog/[slug]` page                     | `slug`, `category`, `reading_time_min` |
| `blog_scroll_depth`    | Per-scroll 25/50/75/100 bucket                       | `slug`, `percent` |
| `blog_read_complete`   | ≥75 % scroll + ≥60 % of expected reading time dwell  | `slug`, `dwell_seconds` |
| `blog_share`           | Delegated share click (`data-blog-share`)            | `slug`, `network` (`twitter`/`whatsapp`/`linkedin`) |
| `blog_copy_link`       | Delegated copy click (`data-blog-copy`)              | `slug` |
| `blog_comment`         | Comments widget first intersects viewport (≥50 %)   | `slug` |
| `blog_newsletter_signup` | Newsletter CTA click (`data-blog-newsletter`)      | `slug` |
| `blog_cta_click`       | CTA click (`data-blog-cta`)                          | `slug`, `name`, `surface` |

### 3.4 AI Tutor (provider via `AiTutorAnalyticsProvider`)

| Event                          | When                                | Properties |
|--------------------------------|-------------------------------------|------------|
| `ai_tutor_open`                | AI Tutor page mount                 | `entry_path` |
| `ai_tutor_mode_switch`         | User switches study/explain/etc.    | `from_mode`, `to_mode` |
| `ai_tutor_conversation_start`  | First user message in a session     | `mode`, `provider` |
| `ai_tutor_message`             | Each user/assistant turn            | `role`, `tokens`, `latency_ms`, `provider` |
| `ai_tutor_feedback`            | Thumbs up/down                      | `vote`, `message_id` |
| `ai_explanation_open`          | Open inline AI explanation          | `question_id`, `topic` |
| `ai_explanation_feedback`      | Feedback on an inline explanation   | `question_id`, `vote` |

### 3.5 Question Bank (`ExamQuestionBank.tsx` + others)

| Event                  | When                                | Properties |
|------------------------|-------------------------------------|------------|
| `question_view`        | Question card rendered              | `question_id`, `topic`, `subject`, `year` |
| `question_solve`       | User submits an answer              | `question_id`, `topic`, `is_correct`, `time_seconds` |
| `question_skip`        | User moves past without answering   | `question_id`, `topic` |
| `question_bookmark`    | Bookmark toggle                     | `question_id`, `action` |
| `question_note_add`    | Note saved                          | `question_id`, `note_length` |

### 3.6 Leaderboard

| Event                  | When                                | Properties |
|------------------------|-------------------------------------|------------|
| `leaderboard_view`     | First mount of `/leaderboard`       | `period` |
| `leaderboard_tab_switch` | User switches all/weekly/monthly  | `from_period`, `to_period` |

### 3.7 Subscription & payments

| Event                  | When                                | Properties |
|------------------------|-------------------------------------|------------|
| `subscription_intent`  | Plan CTA click (`data-subscription-cta`) | `plan`, `surface` |
| `payment_success`      | Razorpay success callback           | `plan`, `amount_inr`, `coupon` |
| `payment_failure`      | Razorpay failure callback           | `plan`, `reason` |
| `coupon_applied`       | Coupon applied at checkout          | `code`, `discount_pct` |

---

## 4. Backend: `AnalyticsEvent` Table

`backend/analytics/models_events.py` — append-only event store for the
internal admin dashboard. Lives alongside the existing aggregated
`DailyMetrics` etc.

| Column         | Type           | Notes                                 |
|----------------|----------------|---------------------------------------|
| `id`           | BigAutoField   | Primary key                           |
| `event_id`     | UUID           | Client-supplied idempotency key       |
| `event_name`   | str(64)        | Indexed; one of the union types above |
| `user_id`      | int (nullable) | When authenticated                    |
| `visitor_id`   | str(64)        | Indexed; localStorage UUID            |
| `session_id`   | str(64)        | Indexed; sessionStorage UUID          |
| `path`         | str(512)       | URL path                              |
| `page_type`    | str(64)        | Indexed; from `pageClassifier`        |
| `page_group`   | str(64)        | Indexed                                |
| `utm_*`        | str(128)       | source/medium/campaign/term/content   |
| `device_type`  | str(32)        | mobile/desktop/tablet                 |
| `browser`      | str(32)        | Chrome/Safari/Firefox/Edge/...        |
| `os`           | str(32)        | iOS/Android/Windows/macOS/Linux       |
| `language`     | str(8)         | First language tag                    |
| `country`      | str(64)        | Indexed; from IP geolocation (server) |
| `referrer`     | str(512)       | document.referrer                     |
| `properties`   | JSONField      | Event-specific blob, 8 KB cap         |
| `created_at`   | DateTime       | Indexed                               |
| `received_at`  | DateTime       | `auto_now_add` — server ingest time  |

Composite indexes: `(event_name, created_at)`, `(page_type, created_at)`,
`(page_group, created_at)`, `(utm_campaign, created_at)`,
`(country, created_at)` — all server-side aggregations land on an index.

---

## 5. Internal Admin Dashboard

URL: **`/admin/analytics-dashboard`** — admin-only (redirects non-admins
to `/dashboard`). Single fetch from
`GET /api/analytics/admin/dashboard-data/`, auto-refresh every 60 s.

KPIs:

| Card                  | Definition                                                   |
|-----------------------|--------------------------------------------------------------|
| **Active now**        | Unique visitors with any event in the last 5 min             |
| **Today — Users**     | Unique `visitor_id` since 00:00 local                        |
| **Today — Page views**| Total `page_view` events since 00:00 local                   |
| **Today — Sign-ups**  | Count of `sign_up` events since 00:00 local                  |
| **Today — Revenue**   | `sum(amount_inr)` over `payment_success` since 00:00         |
| **Weekly / Monthly**  | Same four metrics over 7 / 30 day windows                    |

Sections:

- **Daily-active bar chart** — 30 days, TruncDate aggregation, hover
  tooltips.
- **Conversion funnel** — `landing → blog → question → ai → register
  → sign_up → checkout → paid`, each stage rendered as a relative %
  bar.
- **Top pages (25)** — `page_view` count by `page_type`.
- **Top blogs (10)** — `blog_view` count by `slug`.
- **Top searches (15)** — `search_query` count.
- **Top countries** — by `country`.
- **Devices / Browsers** — by `device_type` / `browser`.
- **UTM campaigns** — by `utm_campaign` (excluding `(not set)`).

The view at `backend/analytics/views_internal.py:AnalyticsDashboardDataView`
runs all aggregations server-side. No client-side crunching.

---

## 6. SEO Tracking

SEO is **not** a separate pipeline — it's a section of the GA4 standard
report plus internal admin data:

- **Indexing** — submitted sitemaps are observed in
  [Google Search Console](https://search.google.com/search-console);
  health is checked by the existing `seo.ts` library on the frontend.
- **CWV** — `frontend/src/lib/seo.ts` reports `LCP/INP/CLS` via the
  existing `web-vitals` integration; these land as GA4 events
  automatically through `gtag('event', ...)`.
- **Top ranking keywords / search queries** — surfaced by GA4
  Acquisition → Google Organic Search report. We additionally
  forward every `search_query` client event to the internal backend
  so admins can see what users search *within* the app.
- **Indexed status / last crawl** — server-rendered `<link rel="canonical">`
  + sitemap (`/sitemap.xml` + `/sitemap-*.xml`) + `robots.txt`. Verified
  via `seo.ts`'s on-page checks.

No new tracking scripts; SEO is a *report* over the data we already
capture.

---

## 7. Attribution

`analytics.attribution` reads `?utm_source=...` (and the rest of the
UTM params) on every page view, persists them to
`localStorage.crackcms_attribution_v1` with a **30-day TTL**, and merges
them into every subsequent event.

Attribution survives:

- Same-domain navigation (user opens blog → reads question).
- Page reloads (same tab, same session).
- Returning visits within 30 days (read from localStorage).
- Cross-tab (visitor_id is shared across tabs).

Attribution is **reset** when the user opens a new tab from a fresh
referrer with new UTMs.

---

## 8. Environment Variables

| Variable                                | Required | Purpose                          |
|-----------------------------------------|----------|----------------------------------|
| `NEXT_PUBLIC_GA_MEASUREMENT_ID`         | yes      | GA4 measurement ID               |
| `NEXT_PUBLIC_CLARITY_PROJECT_ID`        | optional | Microsoft Clarity project ID     |
| `NEXT_PUBLIC_POSTHOG_KEY`               | optional | PostHog project API key          |
| `NEXT_PUBLIC_POSTHOG_HOST`              | optional | PostHog host (default `https://us.i.posthog.com`) |
| `NEXT_PUBLIC_ANALYTICS_IN_DEV`          | optional | Set `true` to enable in dev      |
| `NEXT_PUBLIC_DD_APPLICATION_ID` (etc.)  | optional | Datadog RUM (already configured) |
| Backend: `DISABLE_RAG`                  | n/a      | Independent of analytics         |

If a vendor key is missing, that vendor's loader renders `null` and the
helper (`safeGtag`/`safeClarity`/`safePosthog`) silently no-ops. No
errors, no broken scripts.

---

## 9. Verification

### 9.1 Type / lint / build

```bash
cd frontend
npx tsc --noEmit --skipLibCheck     # 0 errors
npm run lint                         # 0 errors (pre-existing warnings)
npm run build                        # /admin/analytics-dashboard builds static
```

```bash
cd backend
python manage.py check               # 0 issues
python manage.py migrate             # 0006_analytics_event applied
```

### 9.2 GA4 DebugView

1. Install [Google Analytics Debugger](https://chrome.google.com/webstore/detail/google-analytics-debugger/jnkmfdileelhofjcijamephohjechhna).
2. Open `cracklabs.app` — `page_view` should appear once per route
   change with `page_type`/`page_group` custom dimensions.
3. Confirm **no duplicate** `page_view` on initial load (we use GA4's
   `send_page_view: false` and fire manually from React).
4. Check scroll: scrolling 25 / 50 / 75 / 100 % triggers
   `scroll_depth` once per bucket per page.

### 9.3 Microsoft Clarity

1. Visit `clarity.microsoft.com` → select project.
2. Recordings tab — should populate within minutes of consenting to
   `marketing` cookies.
3. Heatmaps tab — render after enough page views.
4. Dead-click / rage-click signals appear after ~24 h of traffic.

### 9.4 PostHog

1. Visit `us.i.posthog.com` → Activity → Live events.
2. Confirm `page_view`, `blog_view`, `question_solve`, `payment_success`
   arrive with `page_type`, `utm_source`, `country`, `browser` props.
3. Build a funnel: `page_view → question_view → question_solve →
   sign_up → payment_success`. Drop-off should appear at each stage.

### 9.5 Internal admin dashboard

1. Sign in as an admin (email allowlist).
2. Open `/admin/analytics-dashboard`.
3. "Active now" should reflect your session within seconds; reload
   the page — KPIs and chart refresh.

---

## 10. Dashboards Summary

| Vendor / Surface         | Dashboards                                                                 |
|--------------------------|----------------------------------------------------------------------------|
| **GA4**                  | Acquisition (channels, campaigns), Engagement (pages, scroll), Monetisation (events), Tech (devices, browsers), Demographics (countries) — via `page_type`/`page_group` custom dimensions |
| **Microsoft Clarity**    | Heatmaps, session recordings, dead-click map, rage-click counter            |
| **PostHog**              | Funnels (sign-up, payment, AI tutor adoption), retention cohorts, feature flags, A/B test results |
| **Internal `/admin/analytics-dashboard`** | Realtime KPIs, daily-active chart, conversion funnel, top pages/blogs/searches/countries/devices/browsers/campaigns |
| **Google Search Console**| Indexing, search queries, backlinks, mobile usability, Core Web Vitals (linked from `frontend/src/lib/seo.ts`) |

---

## 11. Implementation Checklist (shipped in `57f4dfb`)

- [x] Unified typed analytics surface (`frontend/src/lib/analytics.ts`).
- [x] Single source of truth: `TrafficAnalytics.tsx` fires page_view,
      scroll, time-on-page, outbound, exit, errors — deduped.
- [x] Microsoft Clarity loader (`ClarityInit.tsx`) — consent-gated.
- [x] PostHog loader (`PostHogInit.tsx`) — consent-gated.
- [x] ConsentBanner with three categories and granular toggles.
- [x] pageClassifier mapping 60+ routes to stable IDs.
- [x] BlogAnalytics overlay: view / scroll / read-complete / share /
      copy / comment / CTA.
- [x] AiTutorAnalytics provider: mode / conversation / message /
      feedback.
- [x] LeaderboardAnalytics: view / tab switch.
- [x] SubscriptionAnalytics helpers + delegated CTA capture.
- [x] AnalyticsEvent append-only table + composite indexes.
- [x] AnalyticsIngestView (public, throttled) +
      AnalyticsDashboardDataView (admin-only).
- [x] `/admin/analytics-dashboard` admin BI UI with 60s auto-refresh.
- [x] Lint clean, typecheck clean, `manage.py check` clean,
      `next build` successful.
- [x] Migration `0006_analytics_event` applied.
- [x] Pushed to `origin/main` on `https://github.com/Divyanshu1Dubey/Crack_Me_AI`.

---

## 12. Future Work

- **Server-side geo lookup** — currently `country` is empty for events
  with no client header; integrate a MaxMind lookup in
  `AnalyticsIngestView` (`X-Forwarded-For` aware).
- **A/B testing** — PostHog feature flags already support it; add a
  thin React helper (`useFlag`) and a couple of high-leverage tests
  (pricing copy, AI tutor default mode).
- **Sampling rules** — at >100k events/day, sample internal relay at
  10 % for non-conversion events; keep 100 % for conversions.
- **Alerting** — PostHog insight → Slack webhook when `payment_failure`
  rate spikes or DAU drops >20 % day-over-day.
- **SLO dashboards** — Datadog RUM already captures LCP/INP/CLS; pipe
  to a dedicated SRE dashboard.