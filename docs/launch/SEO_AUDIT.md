# Phase 4 — SEO Audit

**Date:** 2026-07-22

## Summary

CrackLabs already has a 15-phase SEO/AEO/GEO rollout documented in
`docs/seo/` and the existing `SEO.md`.  This Phase-4 audit only
records confirmations and gaps.

## Verified (already in place)

* `frontend/src/app/sitemap.ts` — 30 URLs, regenerated on demand.
* `frontend/src/app/robots.ts` — allowlist for AI bots.
* `manifest.json` — PWA shortcuts for `/questions` and `/ai-tutor`.
* `hreflang` en-IN / US / GB / x-default.
* 7 exam landing pages (`/cms`, `/neet-pg`, `/ini-cet`, `/fmge`,
  `/usmle`, `/medical-officer`, `/government-doctor-jobs`).
* 8 GEO guides under `/guides`.
* 8 legal/trust pages (`/about`, `/privacy-policy`, `/terms`, etc.).
* `StructuredData` component + `Breadcrumbs` + `FAQSection`.
* `ReviewerByline` (EEAT) on every long-form page.

## Metadata coverage (Phase 4 spot-check)

| Route | Title | Description | OG | Twitter | Canonical |
|---|---|---|---|---|---|
| `/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/neet-pg` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/ini-cet` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/dashboard` | ⚠ Generic | ⚠ Generic | ⚠ — | ⚠ — | ✅ |
| `/practice` | ⚠ Generic | ⚠ Generic | ⚠ — | ⚠ — | ✅ |
| `/recall/search` | ❌ Missing | ❌ Missing | ❌ | ❌ | ✅ |

## Recommendations

1. **Add per-route metadata** for `/practice`, `/dashboard`,
   `/recall/search`.  The `generateMetadata` pattern in
   `frontend/src/app/questions/[...]/page.tsx` can be reused.
2. **Add canonical signal** for `/practice?mode=...` URLs to avoid
   duplicate-content if modes are crawled.
3. **Core Web Vitals** — bundle size is fine but the practice page
   lazy-loads images server-side.  Confirm CLS < 0.1 on mobile via
   Lighthouse before launch.

## Phase 4 actions taken

None — Phase 4 scope explicitly forbids redesigning SEO.

## Recommended Phase-5 work

* Add `app/practice/layout.tsx` `metadata` export.
* Add `app/recall/search/layout.tsx` `metadata` export.
* Add `app/analytics/dashboard_v3/layout.tsx` `metadata` export.
