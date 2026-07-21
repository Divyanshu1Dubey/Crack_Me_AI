# Landing Page Report — CrackCMS

**Date:** July 21, 2026

---

## Overview

Seven exam-specific landing pages were built to dominate SEO for primary keywords:

| URL | Target keyword | Volume | Status |
|---|---|---|---|
| `/cms` | UPSC CMS preparation | 14,800/mo | ✅ Live |
| `/neet-pg` | NEET PG preparation | 49,500/mo | ✅ Live |
| `/ini-cet` | INI-CET preparation | 8,100/mo | ✅ Live |
| `/fmge` | FMGE preparation | 6,600/mo | ✅ Live |
| `/usmle` | USMLE Step 1 for Indian MBBS | 33,100/mo | ✅ Live |
| `/medical-officer` | Medical Officer recruitment | 12,100/mo | ✅ Live |
| `/government-doctor-jobs` | Government doctor jobs after MBBS | 18,100/mo | ✅ Live |

---

## Section Structure (uniform across all 7)

1. **Hero** — accent gradient, badge, headline, tagline, 4 hero bullets, dual CTA, stats grid (4 tiles)
2. **Stat tiles** (light variant for repeat)
3. **Why CrackCMS** — 6 feature cards (AI tutor, PYQs, mock tests, textbook links, gamified streaks, offline-friendly)
4. **Exam Pattern** — table with 7 rows (papers, questions, time, marks, negative marking, mode, subjects)
5. **Eligibility** — table with 5 rows
6. **Syllabus** — table with subject / weight / high-yield topics (6-9 rows)
7. **Recommended Books** — 4-6 book cards with author + rationale
8. **FAQ** — 6-8 expandable Q&A
9. **CTA** — final "Ready to crack [exam]?" card
10. **Related Exams** — chip links to other landing pages
11. **Site-wide footer** with 5 columns

---

## SEO On-page Checklist

Every landing page passes:

- [x] Unique `<title>` ≤ 60 chars
- [x] Unique `<meta description>` 120-160 chars
- [x] Single `<h1>`
- [x] Hierarchical H2/H3 (no skipped levels)
- [x] Canonical URL via `alternates.canonical`
- [x] OpenGraph + Twitter card meta tags
- [x] JSON-LD Course schema
- [x] JSON-LD FAQPage schema with 6-8 Q&A
- [x] JSON-LD BreadcrumbList schema
- [x] hreflang tags (en-IN, en-US, en-GB, x-default)
- [x] Internal links to other landing pages + guides
- [x] CTA to /register and /subscription
- [x] Image alt text (where images present)
- [x] Lazy-loaded images
- [x] Server-rendered (zero client JS for above-the-fold)

---

## Content Quality

- 2,500-4,000 words per page
- Tables for pattern, eligibility, syllabus, books
- FAQ blocks answer People Also Ask queries
- Comparison-friendly (subject distribution, cutoff, salary)
- Citations to authoritative sources (UPSC, NBE, NMC, official textbooks)

---

## Conversion Path

Landing page visitor journey:
1. Land on `/cms`
2. Read hero + stats
3. Scroll through syllabus table
4. Open FAQ block (engagement signal)
5. Click "Create free account" CTA
6. Land on /register
7. Sign up (free tier)
8. Use 10 daily AI tokens to try AI tutor
9. Hit token limit → upsell to /subscription

---

## Tracking

For each landing page:
- Organic sessions (GA4, filter by page)
- Bounce rate
- Avg time on page
- Scroll depth
- CTA clicks
- Conversions (signups)
- Keyword rankings (Ahrefs)

---

## Recommended Tests

A/B test ideas:
- Hero CTA copy ("Start Free" vs "Crack [exam] in 6 months")
- Stats grid placement (above vs below hero)
- FAQ collapse default (open vs closed)
- Premium CTA prominence (sidebar vs in-line)
- Book recommendations vs video recommendations
