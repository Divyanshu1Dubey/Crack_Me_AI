# Google Search Console + GA4 Setup for cracklabs.app

> You (the founder) execute these steps once. The codebase is already wired
> to consume the verification codes via environment variables. Total time:
> 15 minutes. All steps are required before ranking improvements begin.

---

## Part A — Google Search Console (GSC)

### A1. Verify ownership (5 min)

1. Open <https://search.google.com/search-console/welcome>
2. Click **URL Prefix** property type → enter `https://www.cracklabs.app` (use `www` form — your `seo.ts` enforces it).
3. Verification method → **HTML tag**. GSC shows you a meta tag like:
   ```html
   <meta name="google-site-verification" content="abc123xyz..." />
   ```
4. Copy the value (`abc123xyz...`).
5. Set the environment variable in Vercel:
   - Vercel Dashboard → Project → Settings → Environment Variables
   - Add `NEXT_PUBLIC_GSC_VERIFICATION` = the verification code
   - Or edit `frontend/src/app/layout.tsx` directly and replace the placeholder
6. Deploy. Re-open `view-source:https://www.cracklabs.app` and confirm the
   `<meta name="google-site-verification">` tag is present in `<head>`.
7. Back in GSC, click **Verify**. Should pass in <60 seconds.

### A2. Submit sitemap (1 min)

1. GSC → left menu → **Sitemaps**
2. Add sitemap URL: `sitemap.xml`
3. Click **Submit**
4. Status should become "Success" within minutes. Coverage = ~50 URLs.

### A3. Add Bing Webmaster Tools (3 min)

1. Open <https://www.bing.com/webmasters>
2. Add `https://www.cracklabs.app` via **URL Prefix**
3. Verification: HTML meta tag — copy code, set `NEXT_PUBLIC_BING_VERIFICATION` env var, deploy, verify.
4. **Sitemaps** → submit `https://www.cracklabs.app/sitemap.xml`
5. **URL Inspection** → paste `https://www.cracklabs.app/cms` → **Request indexing**

### A4. Request indexing for every pillar (5 min)

In GSC → **URL Inspection** → paste each of these → **Request indexing**:

- `https://www.cracklabs.app/`
- `https://www.cracklabs.app/cms`
- `https://www.cracklabs.app/neet-pg`
- `https://www.cracklabs.app/ini-cet`
- `https://www.cracklabs.app/fmge`
- `https://www.cracklabs.app/usmle`
- `https://www.cracklabs.app/medical-officer`
- `https://www.cracklabs.app/government-doctor-jobs`
- `https://www.cracklabs.app/cms/pyq/2024`
- `https://www.cracklabs.app/cms/pyq`
- `https://www.cracklabs.app/cms/subject/medicine`
- `https://www.cracklabs.app/cms/cutoff/2024`
- `https://www.cracklabs.app/cms/vs-neet-pg`
- `https://www.cracklabs.app/cms/books/harrison`
- `https://www.cracklabs.app/cms/strategy/6-month`
- `https://www.cracklabs.app/guides/upsc-cms-complete-guide`

Repeat weekly for new pages you publish.

### A5. Enable CrUX + email alerts (2 min)

1. GSC → **Experience** → **Core Web Vitals** → confirm it's set up (it auto-enables once you have enough traffic)
2. GSC → **Settings** → **Email notifications** → enable:
   - Critical issues (manual actions, security)
   - New backlinks
   - Indexing errors
3. Optional: GSC → **Settings** → **Associated email addresses** → add a personal email for backup

---

## Part B — Google Analytics 4 (GA4)

The codebase is already wired (`NEXT_PUBLIC_GA_MEASUREMENT_ID`). Your job is to:

### B1. Confirm GA is live (1 min)

1. Open <https://analytics.google.com> → your CrackCMS property
2. **Realtime** → open `https://www.cracklabs.app` in another tab → you should see "1 active user" within 10 seconds
3. If not, set `NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX` env var in Vercel (or replace the default `G-MM88RT1QQK` in `layout.tsx`)

### B2. Mark these events as Conversions (2 min)

GA4 → **Admin** (gear icon, bottom-left) → **Conversions** → **New conversion event** → add each name:

| Event name | Fires when |
|---|---|
| `sign_up` | User completes registration |
| `pyq_year_open` | User clicks a year tile in Year Stats panel |
| `mock_test_start` | User enters Exam Mode or Practice Fullscreen |
| `ai_explain_request` | User clicks "Generate AI Analysis" |
| `subscription_intent` | User clicks Subscribe button |
| `register_intent` | User clicks Create free account CTA from public surface |

### B3. Create audiences (3 min)

GA4 → **Admin** → **Audiences** → **New audience** → create:

- **"CMS aspirants"** — sequence: `page_location contains /cms` THEN `event_name = pyq_year_open` (within 7 days)
- **"NEET PG aspirants"** — same, page contains `/neet-pg`
- **"Returning users"** — `event_name = sign_up` (last 30d) AND `event_name = pyq_year_open` (last 7d)

### B4. BigQuery export (optional, 5 min — free tier)

GA4 → **Admin** → **BigQuery links** → link a GCP project. Lets you SQL raw events to find which pages lose users.

### B5. Enable Google Signals (1 min)

GA4 → **Admin** → **Data Streams** → your web stream → **Enhanced Measurement** → enable all toggles. Also **Configure tag settings** → enable **Google Signals** for cross-device tracking.

---

## Part C — Schema validation (1 hour, once)

After deploy, validate your JSON-LD schema on key pages:

1. Open <https://validator.schema.org/>
2. Paste the URL of:
   - `https://www.cracklabs.app/cms` → expect Organization + WebSite + Course + FAQPage + BreadcrumbList
   - `https://www.cracklabs.app/cms/subject/medicine` → expect MedicalWebPage + FAQPage + BreadcrumbList
   - `https://www.cracklabs.app/cms/pyq/2024` → expect Article + FAQPage + BreadcrumbList
   - `https://www.cracklabs.app/cms/strategy/6-month` → expect HowTo + FAQPage + BreadcrumbList
3. Fix any errors before publishing more pages.

Also run Google's Rich Results Test on each: <https://search.google.com/test/rich-results>

---

## Part D — Lighthouse + PageSpeed Insights audit (30 min)

For each pillar page, run Lighthouse and target:

- Performance: ≥90
- Accessibility: ≥95
- Best Practices: ≥95
- SEO: ≥95

Quick checklist:

- All `<img>` tags use `next/image`
- All headings have proper hierarchy (h1 → h2 → h3)
- `lang="en-IN"` on `<html>` (already set)
- Tap targets ≥48px
- Color contrast ≥4.5:1
- Cumulative Layout Shift <0.1

If a page is below 90 Performance, check:

- Are hero images using `priority`?
- Are below-fold sections lazy-loaded?
- Are fonts using `display: swap`? (already configured for Manrope + Space Grotesk)

---

## Part E — Verify pages are being indexed (ongoing)

GSC → **Pages** → see:

- **Indexed pages** (should grow weekly)
- **Why pages aren't indexed** (fix any "Crawled - currently not indexed" by Request Indexing)

GSC → **Enhancements** → check:

- **Breadcrumbs** (your breadcrumb schema should generate valid crumbs)
- **FAQ** (your FAQPage schema should appear here once indexed)
- **Site links search box** (your WebSite schema's SearchAction should trigger this)

---

## TL;DR daily checklist (after the 30-min setup)

- [ ] Check GSC → Pages for indexing errors (1 min)
- [ ] Check GA4 → Realtime for active user spikes (30 sec)
- [ ] Check Ahrefs Webmaster → Backlinks for new links (1 min)
- [ ] Run HARO queries and reply to 1 (10 min)

Total: ~15 min/day keeps your ranking telemetry tight.