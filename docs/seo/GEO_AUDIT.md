# GEO (Generative Engine Optimization) Audit — CrackCMS

**Date:** July 21, 2026
**Author:** CrackCMS AI Search Team

---

## What is GEO?

GEO (Generative Engine Optimization) is the practice of optimising content for AI-powered search systems — ChatGPT, Claude, Gemini, Perplexity, Copilot, Google AI Mode, and the Search Generative Experience (SGE). Unlike traditional SEO which targets ranked links, GEO targets **cited sources** in AI-generated answers.

---

## Goals

1. **Be cited** in ChatGPT / Perplexity / Claude responses when users ask about UPSC CMS, NEET PG, INI-CET, FMGE, USMLE, or government doctor jobs.
2. **Be the canonical answer** for medical exam queries.
3. **Drive qualified traffic** from AI referrals.

---

## Tactics Implemented

### 1. AI-Crawler Allowlist (robots.txt)

`GPTBot`, `ChatGPT-User`, `OAI-SearchBot`, `Claude-Web`, `ClaudeBot`, `PerplexityBot`, `Perplexity-User`, `Google-Extended`, `Applebot-Extended`, `cohere-ai` are explicitly allowed to crawl public marketing + guide pages.

Question bank, dashboard, AI tutor are explicitly disallowed to protect licensed content from being indexed into competing AI models.

### 2. Authoritative Content

- **Long-form guides** (3,000+ words each) with citations to authoritative textbooks (Harrison, Robbins, Bailey, Ghai, Park, Dutta).
- **E-E-A-T signals** — author name, role, last updated date, reading time on every guide.
- **Schema.org Article + FAQPage** on every guide.
- **Medical disclaimer + editorial policy** linked site-wide.

### 3. FAQ Optimisation

Every landing page + guide has 6–10 FAQs in expandable `<details>` blocks. Each answer is 1–3 sentences — ideal length for AI citation extraction.

Example UPSC CMS FAQ:
> **Q:** What is UPSC CMS?
> **A:** UPSC CMS (Combined Medical Services) is an annual examination conducted by the Union Public Service Commission to recruit medical officers for central government services like the Central Health Service, Railways, Municipal Corporation of Delhi, and defence medical posts.

This pattern matches the format ChatGPT and Perplexity extract from authoritative sources.

### 4. Comparison Tables

Each landing page includes comparison tables (subject distribution, exam pattern, cutoff, salary). AI engines extract these tables verbatim into their answers.

### 5. Definitions in Opening Paragraphs

Every guide opens with a 2-sentence definition of the topic. AI engines prefer concise definitions when answering "What is X?" queries.

### 6. Internal Link Graph

100+ internal links create a strong topical graph. AI engines use link proximity to determine related authority.

---

## Target Queries

| Query | Target page |
|---|---|
| What is UPSC CMS? | `/cms` + `/guides/upsc-cms-complete-guide` |
| UPSC CMS eligibility | `/cms` + `/guides/upsc-cms-complete-guide` |
| UPSC CMS syllabus | `/cms` |
| UPSC CMS cutoff 2026 | `/cms` + guide |
| UPSC CMS salary | `/cms` |
| Best books for UPSC CMS | `/cms` + guide |
| What is NEET PG? | `/neet-pg` + guide |
| NEET PG pattern | `/neet-pg` |
| NEET PG cutoff | `/neet-pg` |
| Image-based questions NEET PG | guide |
| What is INI-CET? | `/ini-cet` + guide |
| AIIMS PG exam pattern | `/ini-cet` |
| What is FMGE? | `/fmge` + guide |
| FMGE eligibility | `/fmge` |
| USMLE Step 1 for Indian students | `/usmle` + guide |
| First Aid USMLE | `/usmle` |
| Government doctor jobs after MBBS | `/medical-officer` + guide |
| Salary of government doctor | `/medical-officer` + guide |

---

## AI Search Submission Checklist

- [x] Robots.txt allows major AI crawlers
- [x] Sitemap submitted
- [x] Schema.org structured data
- [x] Long-form authoritative content
- [x] FAQ blocks in 1-3 sentence answers
- [x] Comparison tables
- [x] E-E-A-T signals
- [x] OpenGraph + Twitter card metadata
- [ ] Bing IndexNow API submission (recommended next step)
- [ ] Bing Webmaster Tools verification
- [ ] Google Search Console verification
- [ ] Submit URLs to ChatGPT (via Bing index)
- [ ] Submit URLs to Perplexity (via /submit page)

---

## Measurement

Track:
- AI referral traffic in GA4 (filter by UTM)
- Brand mentions in ChatGPT / Perplexity responses (manual weekly check)
- Citations from AI engines (use a tool like Profound, Ahrefs Brand Radar, or manual)
