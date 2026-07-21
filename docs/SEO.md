# SEO Audit

> SEO audit covering titles, descriptions, structured data, OpenGraph, Twitter Cards, canonical URLs, internal linking, robots.txt, sitemap, schema.org, Core Web Vitals, accessibility, image optimization, lazy loading, and SEO opportunities.

---

## Executive Summary

| Area | Status | Notes |
|---|---|---|
| Titles | ✓ Mostly OK | `seo.ts` provides brand constants; verify per-page overrides |
| Meta descriptions | ⚠ Verify | Some pages may use auto-generated ones |
| Structured data (JSON-LD) | ⚠ Missing | No schema.org markup found |
| OpenGraph | ✓ Implemented | `seo.ts` + `defaultOgImage` |
| Twitter Cards | ⚠ Verify | Need `twitter:card`, `twitter:site`, `twitter:title`, `twitter:description`, `twitter:image` |
| Canonical URLs | ⚠ Verify | Not explicitly set in metadata |
| Internal linking | ⚠ Audit | Many routes but cross-links may be sparse |
| `robots.txt` | ✓ Implemented | `app/robots.ts` |
| `sitemap.xml` | ✓ Implemented | `app/sitemap.ts` (must be reviewed for completeness) |
| Schema.org | ✗ Missing | Add Course, Quiz, FAQPage, Organization, BreadcrumbList |
| Core Web Vitals | ⚠ Unmeasured | Add Lighthouse CI / Datadog RUM |
| Accessibility | ⚠ Audit | WCAG AA — verify color contrast, keyboard nav, alt text |
| Image optimization | ✓ `next/image` used in landing | Verify across all pages |
| Lazy loading | ✓ `dynamic()` used | Verify on all heavy routes |

---

## 1. Titles

### Current pattern

- Brand: `CrackLabs` / `crack-me-ai`
- Default title from `lib/seo.ts`: `siteTitle`, `defaultOgImage`, `siteDescription`

### Audit checklist

- [ ] Every page has a unique `<title>` (50–60 chars)
- [ ] Primary keyword appears in title
- [ ] Brand appended (e.g. `UPSC CMS Question Bank | CrackLabs`)
- [ ] No keyword stuffing

### Recommended titles

| Page | Recommended Title |
|---|---|
| `/` | CrackLabs — AI-Powered UPSC CMS Exam Prep |
| `/questions` | 2000+ UPSC CMS MCQs with AI Explanations \| CrackLabs |
| `/ai-tutor` | AI Tutor for UPSC CMS — RAG-Grounded Answers \| CrackLabs |
| `/flashcards` | SM-2 Spaced Repetition Flashcards \| CrackLabs |
| `/tests` | Adaptive UPSC CMS Tests \| CrackLabs |
| `/simulator` | UPSC CMS PYQ Simulator — Real Exam Conditions \| CrackLabs |
| `/analytics` | Performance Analytics Dashboard \| CrackLabs |
| `/roadmap` | Personalized Study Plan \| CrackLabs |
| `/textbooks` | Indexed Medical Textbook Library \| CrackLabs |
| `/login` | Sign In \| CrackLabs |
| `/register` | Start Free \| CrackLabs |

---

## 2. Meta Descriptions

### Audit checklist

- [ ] Every page has a `<meta name="description">` (140–160 chars)
- [ ] Includes call-to-action
- [ ] No truncation risk

### Recommended descriptions

| Page | Description |
|---|---|
| `/` | Practice 2000+ UPSC CMS MCQs with AI explanations grounded in standard textbooks. Start free today. |
| `/questions` | Filter PYQs by year, subject, and topic. Get AI-powered explanations in seconds. |
| `/ai-tutor` | Chat with an AI tutor that has read every UPSC CMS textbook. RAG-grounded answers. |
| `/flashcards` | Master every topic with SM-2 spaced repetition flashcards. Track retention. |
| `/analytics` | Visualize your performance, find weak topics, and predict your score. |
| `/roadmap` | AI-generated study plan tailored to your weak areas. |

---

## 3. Structured Data (JSON-LD)

### Currently missing

The frontend should inject JSON-LD for key page types.

### Recommended additions

| Page | Schema.org Type | Properties |
|---|---|---|
| `/` | `Organization` | name, url, logo, sameAs (social), contactPoint |
| `/` | `WebSite` | name, url, potentialAction (SearchAction) |
| `/questions` | `Quiz` | about, educationalAlignment, hasPart |
| `/textbooks/<id>` | `Book` | name, author, isbn, bookFormat |
| `/ai-tutor` | `Course` | name, description, provider |
| `/roadmap` | `LearningResource` | educationalLevel, teaches, timeRequired |
| All pages | `BreadcrumbList` | itemListElement |

### Example (`Organization`)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "CrackLabs",
  "url": "https://crack-me-ai1.vercel.app",
  "logo": "https://crack-me-ai1.vercel.app/logo.png",
  "sameAs": [
    "https://twitter.com/cracklabs",
    "https://www.linkedin.com/company/cracklabs"
  ]
}
</script>
```

### Implementation

Add a `<StructuredData>` component to `layout.tsx` that takes a `type` prop and renders the matching JSON-LD.

---

## 4. OpenGraph

### Currently implemented

`seo.ts` exports `defaultOgImage` (likely a brand image).

### Audit checklist

- [ ] `og:title` — unique per page
- [ ] `og:description` — unique per page
- [ ] `og:image` — 1200×630 px recommended
- [ ] `og:url` — canonical URL
- [ ] `og:type` — `website` / `article` / `book` / `profile`
- [ ] `og:site_name` — `CrackLabs`
- [ ] `og:locale` — `en_IN`

---

## 5. Twitter Cards

### Currently unknown

Need to verify `next-seo` config or `<meta name="twitter:*">` tags.

### Required meta

```html
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:site" content="@cracklabs" />
<meta name="twitter:creator" content="@cracklabs" />
<meta name="twitter:title" content="..." />
<meta name="twitter:description" content="..." />
<meta name="twitter:image" content="..." />
```

---

## 6. Canonical URLs

### Currently unknown

Next.js App Router generates canonical URLs by default if `metadata.alternates.canonical` is set.

### Recommended addition (in `lib/seo.ts`)

```typescript
export const buildCanonical = (path: string) =>
  new URL(path, siteUrl).toString();
```

### Use in pages

```typescript
export const metadata = {
  alternates: { canonical: buildCanonical('/questions') },
};
```

---

## 7. Internal Linking

### Audit checklist

- [ ] Landing page links to /questions, /ai-tutor, /register, /pricing
- [ ] Question detail links to /textbooks, /flashcards, /analytics
- [ ] Dashboard links to /questions, /tests, /analytics, /roadmap
- [ ] Footer present on every page with key links
- [ ] Breadcrumbs on question/textbook pages

### Recommended

- Add a `<Footer>` component with: Home, Questions, AI Tutor, Tests, Flashcards, Pricing, About, Contact, Terms, Privacy.
- Add `<Breadcrumbs>` component on detail pages (with `BreadcrumbList` schema).
- Contextual in-content links: e.g. on a question explanation, link to the related topic and textbook.

---

## 8. `robots.txt`

### Currently implemented

`frontend/src/app/robots.ts` returns Next.js metadata route.

### Verify

- [ ] Allow all major crawlers
- [ ] Block `/admin`, `/api`, `/auth/*`
- [ ] Reference `sitemap.xml` location

```typescript
// app/robots.ts
export default function robots() {
  return {
    rules: [
      { userAgent: '*', allow: '/', disallow: ['/admin', '/api/', '/auth/'] },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
```

---

## 9. Sitemap

### Currently implemented

`frontend/src/app/sitemap.ts`.

### Audit checklist

- [ ] Includes all public pages
- [ ] Excludes `/admin`, `/login`, `/register`, `/settings`
- [ ] `lastModified` set from DB for question/topic pages
- [ ] `changeFrequency` set (`daily` for landing, `weekly` for static, `monthly` for archived)
- [ ] `priority` set (1.0 for landing, 0.8 for /questions, etc.)

### Implementation

```typescript
// app/sitemap.ts
export default async function sitemap() {
  const base = [
    { url: `${siteUrl}/`, lastModified: new Date(), changeFrequency: 'daily', priority: 1.0 },
    { url: `${siteUrl}/questions`, changeFrequency: 'daily', priority: 0.9 },
    { url: `${siteUrl}/ai-tutor`, changeFrequency: 'weekly', priority: 0.8 },
    // ...
  ];
  const subjects = await fetch(`${API_BASE}/questions/subjects/`).then(r => r.json());
  const subjectPages = subjects.map(s => ({
    url: `${siteUrl}/questions?subject=${s.id}`,
    changeFrequency: 'weekly',
    priority: 0.6,
  }));
  return [...base, ...subjectPages];
}
```

---

## 10. Schema.org / Rich Results

### Currently missing

### Recommended schema

| Page | Schema | Why |
|---|---|---|
| `/` | `Organization`, `WebSite`, `FAQPage` | Brand recognition in SERPs |
| `/questions` | `Quiz` (collection), `Question` (each MCQ) | "People also ask" features |
| `/ai-tutor` | `Course` | Course card in SERPs |
| `/textbooks` | `Book` | Book previews in SERPs |
| `/roadmap` | `LearningResource` | Education-specific results |
| `/tests/<id>` | `Quiz` | Quiz-specific SERP |
| `/flashcards` | `LearningResource` | Flashcard SERPs |

---

## 11. Core Web Vitals

### Targets

| Metric | Target | Current (estimated) |
|---|---|---|
| **LCP** (Largest Contentful Paint) | < 2.5 s | Unknown — measure |
| **INP** (Interaction to Next Paint) | < 200 ms | Unknown |
| **CLS** (Cumulative Layout Shift) | < 0.1 | Unknown |
| **TTFB** | < 800 ms | Unknown |
| **FCP** | < 1.8 s | Unknown |

### Measurement

- Lighthouse CI in GitHub Actions
- Datadog RUM (`@datadog/browser-rum`) configured in layout
- Chrome User Experience Report (CrUX)

### Common fixes

- Preload fonts (`next/font` does this)
- Lazy-load below-the-fold images (`next/image` with `loading="lazy"`)
- Avoid layout shifts from dynamic content (skeleton loaders)
- Minimize main-thread blocking (move heavy computation to web workers)

---

## 12. Accessibility (WCAG 2.1 AA)

### Audit checklist

- [ ] Color contrast ratio ≥ 4.5:1 for text, ≥ 3:1 for large text
- [ ] All interactive elements keyboard-navigable
- [ ] Visible focus indicator
- [ ] ARIA labels on icon-only buttons (e.g. close, search)
- [ ] All images have `alt` text
- [ ] Form labels associated with inputs (`<label htmlFor>`)
- [ ] Error messages announced to screen readers (`aria-live="polite"`)
- [ ] Skip-to-content link
- [ ] Language attribute set (`<html lang="en">` — verify in layout)
- [ ] Color is not the only signal (e.g. error states also have icons/text)
- [ ] Video/audio has captions / transcripts

### Specific pages to audit

- `/questions` (filter UI, question text, options)
- `/ai-tutor` (chat history, AI responses)
- `/tests/<id>` (timer, question navigation)
- `/admin` (tables, modals)

---

## 13. Image Optimization

### Audit

- [ ] Every `<img>` replaced with `<Image>` from `next/image`
- [ ] `width`/`height` set to prevent CLS
- [ ] `alt` text on every image
- [ ] Above-the-fold images use `priority`
- [ ] Below-the-fold use `loading="lazy"`
- [ ] SVG icons inlined or sprite
- [ ] WebP / AVIF served automatically (Next.js does this)

### Tool

`grep -rE "<img " frontend/src/` — should return zero hits outside icon manifests.

---

## 14. Lazy Loading

### Audit checklist

- [ ] Heavy components behind `next/dynamic` with `{ ssr: false }` for client-only widgets
- [ ] Charts (`recharts`) lazy-loaded on analytics/trends pages only
- [ ] `react-markdown` lazy-loaded on AI tutor + question detail
- [ ] Admin page tabs lazy-loaded
- [ ] Datadog RUM initialized with `defer: true`

---

## 15. URL Structure

### Current

```
/questions/{id}                  # ❌ not in Next.js — likely modal route
/tests/[id]
/textbooks
/exams
```

### Recommended

```
/questions?subject=X&topic=Y&year=Z          # filter via query string (current)
/textbooks/[id]                              # textbook detail
/questions/[id]/explanation                  # explanation view (deep linkable)
/ai-tutor/[sessionId]                        # chat history shareable
/roadmap/[id]                                # saved roadmap
/flashcards/[id]/review                      # review session
```

Each deep link should be crawlable + indexable.

---

## 16. Internationalization (i18n)

### Current state

Single-language (English).

### Recommended when scaling

- Add `hreflang` for English-IN variants
- Use `next-intl` for translations
- Currency `INR` already correct for Razorpay integration

---

## 17. Local SEO (if applicable)

- Google Business Profile (if CrackLabs has a physical presence)
- Schema.org `LocalBusiness` markup (if applicable)
- India-specific: IndiaMART, JustDial listings

---

## 18. Backlink & Off-Page

| Strategy | Priority |
|---|---|
| Publish "How to prepare for UPSC CMS" articles on Medium / Dev.to | High |
| Partner with medical colleges for backlinks | Medium |
| YouTube channel with question walkthroughs | High |
| Reddit r/IndianMedicalStudents, r/UPSC | Medium |
| Telegram study groups | High |
| Quora answers with link | Medium |

---

## 19. Performance / SEO quick wins

| Action | Effort | SEO Impact |
|---|---|---|
| Set canonical URLs on every page | 2 hours | High |
| Add Organization + WebSite JSON-LD on landing | 2 hours | High |
| Lazy-load `recharts` and `react-markdown` | 2 hours | High |
| Add FAQPage schema on landing | 2 hours | High |
| Verify all images use `<Image>` | 2 hours | High |
| Add alt text audit | 1 day | Medium |
| Lighthouse CI in GitHub Actions | 1 day | Medium |
| Switch to `next-seo` (or keep App Router metadata) | 1 day | Low |

---

## 20. Monitoring

| Metric | Tool |
|---|---|
| Organic clicks / impressions | Google Search Console |
| Keyword rankings | Ahrefs / SEMrush / Search Console |
| Core Web Vitals | Datadog RUM + Lighthouse CI |
| Crawl errors | Search Console |
| Backlinks | Ahrefs |
| Lighthouse score | Lighthouse CI on every PR |

---

## 21. See Also

- [`PERFORMANCE.md`](./PERFORMANCE.md) — CWV overlaps with performance
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — `vercel.json`, `next.config.ts`, `sitemap.ts`, `robots.ts`
- [`IMPROVEMENTS.md`](./IMPROVEMENTS.md) — SEO items appear in the Top 100 list
