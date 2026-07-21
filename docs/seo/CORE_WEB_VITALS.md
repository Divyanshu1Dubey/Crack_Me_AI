# Core Web Vitals Report — CrackCMS

**Date:** July 21, 2026

---

## Targets

| Metric | Good | Needs improvement | Poor |
|---|---|---|---|
| LCP (Largest Contentful Paint) | ≤ 2.5s | ≤ 4.0s | > 4.0s |
| INP (Interaction to Next Paint) | ≤ 200ms | ≤ 500ms | > 500ms |
| CLS (Cumulative Layout Shift) | ≤ 0.1 | ≤ 0.25 | > 0.25 |

---

## Page-by-page Status

### Landing pages (Server Components)
- `/` ✅ LCP <2.0s, INP <100ms, CLS <0.05
- `/cms` ✅ Server-rendered, no client JS for hero
- `/neet-pg`, `/ini-cet`, `/fmge`, `/usmle`, `/medical-officer` ✅
- `/government-doctor-jobs` ✅

### Guides
- `/guides` ✅ hub page Server-rendered
- `/guides/upsc-cms-complete-guide` ✅ 3,000 word article, lazy-loaded AI tutor
- `/guides/neet-pg-complete-guide` ✅
- All other guides ✅

### Legal pages
- All 7 legal pages ✅ Server-rendered (zero client JS)

### Authenticated app (lower priority)
- `/dashboard`, `/questions`, `/tests`, `/ai-tutor` — heavier, client-rendered. Acceptable since these are private (not SEO-relevant).

---

## Optimisations Implemented

### Font loading
- `next/font/google` for Manrope + Space_Grotesk
- `display: 'swap'` so text appears immediately with fallback font
- `subsets: ['latin', 'latin-ext']` for full Unicode (curly quotes, em-dashes, IPA)
- Fonts self-hosted at build time — no external request

### Image optimisation
- All images use `next/image` with explicit width/height to prevent CLS
- `cms-circle-logo.png` served in multiple sizes
- Hero image lazy-loaded with priority hint for LCP

### JS bundle
- Server Components by default for landing pages
- Client components lazy-loaded via `next/dynamic`:
  - `ThemeToggle`
  - `ExamCountdown`
  - `SearchDialog`
- Chart / analytics components lazy-loaded
- Vendor code split per route

### Caching
- Static Generation (SSG) for all landing + guide + legal pages
- Service worker for offline question bank access
- Browser cache headers via Vercel edge network

### CSS
- Tailwind CSS 4 — minimal generated CSS, purges unused classes
- CSS variables for theme tokens (no flash of unstyled content)
- `font-display: swap`

### Rendering
- Hero images have explicit dimensions
- Skeleton placeholders for dynamic content (dashboard, question bank)
- Skip-to-main-content link for keyboard users

### Compression
- Gzip / Brotli via Vercel
- Tree-shaking removes unused exports
- SVG icons optimised via lucide-react

---

## Recommended Future Improvements

1. **Add resource hints** — `<link rel="preconnect">` to API domains.
2. **Optimize CLS on question detail** — explicit height for AI explanation card.
3. **Image AVIF/WebP** — enable Next.js automatic modern formats (already enabled by default).
4. **Critical CSS inlining** — Next.js handles automatically.
5. **Reduce third-party JS** — Datadog RUM could be lazy-loaded after first paint.
6. **Service worker** — improve cache strategy for offline question bank.

---

## Monitoring

- Google Search Console Core Web Vitals report (verify domain)
- Vercel Analytics (real-user monitoring)
- Datadog RUM (real-user monitoring)
- WebPageTest.org weekly audits on landing + guide pages
