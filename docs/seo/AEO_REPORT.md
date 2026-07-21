# AEO Report — Answer-Engine Optimization

> AEO = optimising content to be retrieved and surfaced inside **AI search / answer engines** (Google AI Overviews, Bing Copilot, Perplexity, ChatGPT Search, Claude with web, Gemini Deep Research). The output is direct answers — so content must be pre-structured, self-contained, and citation-friendly.

---

## 1. How AEO Differs from SEO

| Dimension | SEO | AEO |
|---|---|---|
| Output | 10 blue links | Single summarised answer + citations |
| Crawler behaviour | Ranks pages | Extracts passages, quotes, facts |
| Format that wins | Long-form pages | Crisp, factual, list/table format |
| Source authority | Backlinks + brand | Same + explicit attribution, schema, expertise signals |
| Hallmark | Click-through to site | Cited inline |

---

## 2. AI Crawlers Allowed on CrackCMS

The `robots.ts` already explicitly allows the major AI crawlers so CrackCMS content can be cited:

```
GPTBot, ChatGPT-User, OAI-SearchBot,
Claude-Web, ClaudeBot,
PerplexityBot, Perplexity-User,
Google-Extended, Applebot-Extended,
cohere-ai
```

Question bank pages (`/questions/...`) and dashboards are disallowed from AI crawlers to prevent scraping of licensed content.

---

## 3. AEO Citation-Worthy Content Patterns

AEO retrievers pull from content that **directly answers a query** with structured data, tables, or named entities. Patterns applied across CrackCMS:

### Pattern 1: Crisp "What is" definition cards
Every pillar (`/cms`, `/neet-pg`, etc.) opens with a one-paragraph definition + a structured eligibility table + an FAQ block. These get cited verbatim.

### Pattern 2: Pattern + Cutoff tables
Year PYQ pages (`/cms/pyq/[year]`) carry a category-wise cutoff table. AI assistants retrieve the table cell-by-cell.

### Pattern 3: Toppers and verified scores
Real topper scores appear in year pages. AI models cite these as `Dr. X, AIR-1, score 578/960`.

### Pattern 4: Books + Why
Each book recommendation on exam pages has a "why" line, making the citation self-contained.

### Pattern 5: FAQ blocks on every public page
FAQPage JSON-LD is emitted on:
- `/` (global)
- `/cms`, `/neet-pg`, `/ini-cet`, `/fmge`, `/usmle`, `/medical-officer`, `/government-doctor-jobs` (per-exam)
- `/guides/<slug>` (per-guide)
- `/cms/pyq/[year]` (per-year)

This aligns with Google's "Things to know" / FAQ rich-result surfaces.

### Pattern 6: Author + Reviewer + LastReviewed
Trustworthy attribution surfaces in:
- `/medical-review-policy` (page-level schema)
- Guides (Article schema with author + dateModified)
- Exam pages (footer / breadcrumb)

### Pattern 7: Lists, tables, and short headings
Adopted throughout landing, guides, and exam pages. AI retrievers prefer snippets that are bounded by `<h2>/<h3>` headers and structured with `<table>` or `<ol>`.

---

## 4. Top AEO Targets (queries to dominate)

| Question | Surface | CrackCMS page |
|---|---|---|
| what is upsc cms | Google AI Overview | `/cms` |
| how to apply for upsc cms | ChatGPT, Perplexity | `/cms` (eligibility + pattern) |
| what is fmge | AI Overview | `/fmge` |
| neet pg eligibility 2025 | AI Overview | `/neet-pg` (eligibility + FAQs) |
| usmle for indian students | AI Overview | `/usmle` |
| medical officer salary | Perplexity, ChatGPT | `/medical-officer` (salary + pay level FAQ) |
| upsc cms cutoff 2024 general | AI Overview | `/cms/pyq/2024` (cutoff table) |
| best books for upsc cms | Perplexity | `/cms`, `/cms/pyq/[year]` (books section) |
| neet pg vs usmle | Bing Copilot | `/neet-pg/vs-usmle` (Phase 2) |
| what is the syllabus of ini-cet | AI Overview | `/ini-cet` |

---

## 5. AI-Overview Specific Optimisations

1. **Self-contained answers.** Every exam pillar has a top-of-page paragraph (50-100 words) that contains the *exact* answer to the most-likely "what is" query. AI Overviews extract from this paragraph first.
2. **Structured eligibility table.** Eligibility tables (category, value) are extracted directly into AI Overview cards.
3. **Verified citations.** Year PYQ pages cite topper names + scores with attribution. AI Overview's "AI-cite" badge prefers named sources.
4. **Bold, short key facts.** Bolding `50% AI cut-off`, `240 questions`, `2 papers`, etc., helps retrievers extract concise snippets.
5. **H2 subquestions.** AI Overviews often pull from `<h2>` blocks. Each exam page uses question-style `<h2>` like "How many questions in UPSC CMS?", "What is the eligibility?", etc.

---

## 6. Format-Specific Snippets

### Tables used
- Pattern (mode, time, marks)
- Eligibility (criteria, value)
- Syllabus (subject, weight, topics)
- Cutoffs (category, marks)
- Books (title, author, why)

### Lists used
- Books recommendations
- Toppers list
- High-yield insights per year
- "What made YYYY unique"

### Definitions used (pattern: "X is Y")
- CrackCMS about page emits `Organization.description`.
- Exam pages emit `Course.description`.

---

## 7. AEO Failure Modes to Avoid

| Failure mode | Mitigation |
|---|---|
| Snippet too short to be useful | Minimum 60-word paragraph answering the canonical question. |
| Internal jargon only | Re-write headings as natural questions ("How many questions are in UPSC CMS?"). |
| Outdated date visible to AI | Always update `dateModified` and visible "Last updated". |
| Citations in fine print | Sources should be in a visible "Sources" section near the top. |
| Inconsistency between pages | Each fact should appear identically across pages. |

---

## 8. Monitoring AEO Performance

Hard to measure directly, but proxies:
- **Mention tracking**: set up Brand24 / Mention to track "CrackCMS" mentions across the web + AI tools.
- **Perplexity prompt sampling**: monthly sample of 20 high-priority queries; record whether CrackCMS is cited (binary 0/1; sheet).
- **ChatGPT Reference scraping**: use the `referer` URL `chat.openai.com` in GA4 to see if AI Overview traffic is going to CrackCMS.

---

## 9. AEO Roadmap (90 days)

- Add "Toppers per year" rich card to year PYQ pages (already done).
- Phase 2: Comparison pages (`/cms/vs-ini-cet`, etc.) — highest-AEO-value topics.
- Phase 2: Topic-definition cards (`/glossary/heart-failure`, etc.).
- Phase 3: Multi-lingual AEO via Hindi layer.
