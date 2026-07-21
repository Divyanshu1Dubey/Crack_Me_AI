# Technical SEO Audit — CrackCMS

> Audit performed July 2026 against a live audit of `frontend/src/app/`. Scores are relative to the actual repo state at the time of writing. Items marked ✅ are shipped; 🛠 are shipped in this engagement; ❌ are pending.

---

## 1. Headline Scorecard

| Category | Status | Notes |
|---|---|---|
| Crawl accessibility (`robots.txt`) | ✅ Strong | Clean disallow list, AI-crawler explicit allow |
| Sitemap completeness | ✅ Strong | All indexable public routes present |
| Canonical URLs | ✅ Strong | Per-page `alternates.canonical` set |
| Meta titles | ✅ Strong | Title template + per-page override |
| Meta descriptions | ✅ Strong | All public pages have unique descriptions |
| OpenGraph tags | ✅ Strong | Per-page OG via `ExamLandingLayout` + `pageMetadata` map |
| Twitter Cards | ✅ Strong | All public pages have `summary_large_image` |
| Schema.org JSON-LD | ✅ Strong | Organization + WebSite + SoftwareApplication + Course + FAQPage + BreadcrumbList + Article already injected |
| Heading hierarchy | ✅ Strong | `<h1>` per page, semantic HTML used |
| Image optimization (`next/image`) | ✅ Strong | Used on landing page hero; verify across other routes |
| Core Web Vitals (LCP / INP / CLS) | ⚠️ Unmeasured | Wire up Lighthouse CI + Datadog RUM |
| Internal linking | 🛠 Improved | See `INTERNAL_LINKING_REPORT.md` |
| EEAT signals | ✅ Strong | Editorial policy, medical review policy, About authors, dates |
| Hreflang | ✅ Strong | en-IN, en-US, en-GB, x-default declared in root layout |
| Mobile rendering | ✅ Strong | Mobile-first responsive; Capacitor app shipped |
| Programmatic SEO | 🛠 Shipped 5 year pages + index | See `PyqYearLandingLayout` |

---

## 2. Crawl & Indexing

### robots.txt
- Located at `frontend/src/app/robots.ts`, returns Next.js MetadataRoute API.
- ✅ All authenticated/private routes disallowed.
- ✅ AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended, OAI-SearchBot) explicitly allowed on public content.
- ✅ Sitemap URL declared.

### Sitemap
- Located at `frontend/src/app/sitemap.ts`.
- ✅ Static routes enumerated with correct `priority` + `changeFrequency` per route type.
- 🛠 Updated to include `/exams` and adjust priorities for guide hub and EEAT pages.
- ❌ **Next:** Add dynamic `/<exam>/pyq/[year]` entries once per-year data is approved in production.

### Canonical URLs
- Each public page sets `alternates.canonical`.
- Helper utilities in `frontend/src/lib/metadata.ts` (`buildCanonical`) ensure absolute URLs.

---

## 3. Metadata

### Title template
- Root layout defines: `template: '%s | ${siteName}'`.
- All public pages override their `title` to use this template.
- Recommended length: 50-60 chars. Spot-check the title mapping in `seo.ts` to ensure no truncation.

### Meta descriptions
- ✅ All public pages have unique descriptions via the `pageMetadata` map.
- 🛠 Exam landing pages get unique descriptions from `buildExamMetadata`.

### Keywords
- Root `<meta name="keywords">` set to the global keyword array (33 keywords).
- ✅ Per-page `keywords` arrays on exam landing pages.

---

## 4. Structured Data

JSON-LD injected via Next.js `<Script strategy="beforeInteractive">`. Currently emitted:

| Schema.org type | Page | Notes |
|---|---|---|
| Organization | root | name, url, logo, contactPoint, sameAs |
| WebSite | root | SearchAction -> /questions?search= |
| WebPage | root | home identification |
| SoftwareApplication | root | rating + price |
| Course (CMS / NEET PG) | root | master course nodes |
| FAQPage | root | 5 Q&As |
| BreadcrumbList | root | Home / CMS / NEET PG / Pricing |
| Course + FAQPage + BreadcrumbList | exam pillars | via ExamLandingLayout |
| Article + FAQPage + BreadcrumbList | guides | via GuideLayout |
| AboutPage | /about | entity-rich |
| MedicalWebPage | disclaimer, editorial, medical review | YMYL signaling |
| PrivacyPolicy | /privacy-policy |  |
| TermsOfService | /terms |  |
| Article + FAQPage + BreadcrumbList | /cms/pyq/[year] | via PyqYearLandingLayout |
| CollectionPage | /guides, /cms/pyq | ItemList of children |

### Validation
Manual: enter each route into [Google Rich Results Test](https://search.google.com/test/rich-results) and confirm zero errors.

---

## 5. Internationalization / hreflang

- ✅ Root declares `en-IN`, `en-US`, `en-GB`, `x-default` in `alternates.languages`.
- ✅ Each per-page metadata adds `en-IN` for the canonical of that route.
- ❌ **Future:** Add `hi-IN` (Hindi) translations after the Indic-language versions ship.

---

## 6. Performance (Core Web Vitals)

| Metric | Target | Status | Action |
|---|---|---|---|
| **LCP** | < 2.5 s | Likely OK (homepage uses `<Image priority>` + `next/font`) | Add Lighthouse CI to PR pipeline. |
| **INP** | < 200 ms | Verify | Avoid long tasks in interactive demos; use `next/dynamic`. |
| **CLS** | < 0.1 | OK | All images have dimensions; fonts use `display: 'swap'`. |
| **TTFB** | < 800 ms | OK on Vercel edge | Hit `crackcms-vsthc.ondigitalocean.app` only at fallback. |

**Suggested actions:**
1. Lighthouse CI in `.github/workflows/ci.yml` (run on PR).
2. Datadog RUM is already initialised in `layout.tsx`.
3. Add `next/script` for non-critical third-party tags (already in place).

---

## 7. Image Optimization

- ✅ Hero uses `<Image priority fill sizes>` (`frontend/src/app/page.tsx`).
- ❌ **Audit:** Other public pages need pass to replace raw `<img>` with `<Image>`.

```
grep -rnE "<img " frontend/src/  # should be empty outside icon manifests
```

---

## 8. Accessibility (WCAG 2.1 AA)

| Check | Status |
|---|---|
| `<html lang>` | ✅ `en-IN` |
| Skip link | ✅ `<a href="#main-content">Skip to main content</a>` in layout |
| Main landmark | ✅ `<main id="main-content">` |
| Color contrast | ✅ Brand uses light/dark variants with sufficient contrast |
| Focus indicator | ✅ Tailwind's default focus-visible |
| Form labels | ✅ Contact form labels associated with inputs |
| Heading order | ✅ `<h1>` -> `<h2>` -> `<h3>` sequence preserved across landing, exam, guide layouts |
| Alt text | ✅ Hero image alt; verify everywhere |

---

## 9. URL Structure

Clean, readable, fully indexable URLs.

```
/
  /cms                                <-- exam pillar
    /cms/pyq                          <-- PYQ hub
      /cms/pyq/2020                   <-- year page (programmatic)
      /cms/pyq/2024
  /neet-pg, /ini-cet, /fmge, /usmle   <-- exam pillars
  /medical-officer, /government-doctor-jobs
  /guides                             <-- hub
    /guides/upsc-cms-complete-guide   <-- long-form guide
  /about, /contact, /subscription, /register
  /privacy-policy, /terms, /refund-policy, /cookie-policy, /disclaimer
  /editorial-policy, /medical-review-policy   <-- EEAT
```

---

## 10. Pagination

- Internal Question Bank uses DRF `PageNumberPagination` server-side.
- Frontend public pages don't paginate; they link to /questions or /register.

---

## 11. Broken / Orphan Pages

- ❌ To audit:
  - Dynamic `/questions?exam=<key>&year=<year>` URLs — verify those keys exist.
  - `/jobs` requires auth — correctly noindexed in robots.

---

## 12. Internal Linking

See `INTERNAL_LINKING_REPORT.md`. Summary: The site-wide `<Footer>` provides strong navigational linking. Per-page contextual links need a single coordinated pass.

---

## 13. Pre-Launch Checklist

Before merging any SEO changes:

- [ ] `npm run lint`
- [ ] `npx tsc --noEmit` (or `npm run build` will run typecheck)
- [ ] Test canonicals on dev preview
- [ ] Validate JSON-LD via https://validator.schema.org/
- [ ] Mobile-friendly test on 360×640 viewport
- [ ] Lighthouse desktop & mobile run

---

## 14. Open / Pending Items

| Priority | Item |
|---|---|
| P2 | Add per-state MO pages under `/government-doctor-jobs/[state]` |
| P2 | Subject-wise PYQ pages under `/cms/subject/[slug]` |
| P2 | Cutoff pages under `/cms/cutoff/[year]` and `/<exam>/cutoff` |
| P2 | Hindi translation layer |
| P3 | Lighthouse CI on PR |
| P3 | AMP-style static job-posting pages |
