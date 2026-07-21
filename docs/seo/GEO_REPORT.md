# GEO Report — Generative-Engine Optimization

> GEO = Generative Engine Optimization: the discipline of optimising pages so that **large language models with retrieval** (ChatGPT with Browse, Claude with web search, Gemini with grounding, Perplexity, Copilot, Mistral Le Chat, Google AI Mode) cite CrackCMS when answering a question.

AEO is the answer-engine surface (Google AI Overviews); GEO is the broader LLM-as-search surface. Both share tactics — AEO + GEO tactics are listed in AEO_REPORT.md; this report focuses on the *additional* concerns unique to LLM retrieval.

---

## 1. Why GEO Matters for YMYL Medical Content

For medical YMYL queries, LLM answer engines cite:
- Pages with named authors + visible credentials.
- Pages with `MedicalWebPage` or `HealthTopicContent` schema.
- Pages that use factual, citation-rich prose (not opinion-based).
- Pages that are time-stamped and frequently updated.

CrackCMS already meets all four criteria in its pillar + year pages.

---

## 2. Retrieval-Friendly Page Structure

| Element | CrackCMS status |
|---|---|
| Unique `<title>` per page | ✅ |
| Self-contained opening paragraph answering canonical question | ✅ |
| Inline factual statements (cutoffs, eligibility, dates) | ✅ |
| Lists + tables (LLMs parse these reliably) | ✅ |
| Author + reviewer schema | ✅ via `Article` and `MedicalWebPage` |
| `dateModified` visible + in JSON-LD | ✅ |
| Markdown-like structure (h2 -> h3) | ✅ |

---

## 3. Entity & Knowledge-Graph Considerations

LLMs build internal entity representations. CrackCMS should:
- ✅ Have a unique, identifiable `Organization` node (`siteUrl/#organization`).
- ✅ Reference other entities (UPSC, NBE, AIIMS, USMLE) by canonical name.
- ✅ Use the same name spelling throughout (e.g. "UPSC CMS" not "cms exam upsc" randomly).
- 🛠 `Person` schema for review team members — **pending** (currently bio in HTML only).

---

## 4. Citation Patterns LLMs Prefer

1. **Authoritative source attribution** — every fact should be attributable. CrackCMS sources UPSC / NBE / official notifications and standard textbooks on every exam page.
2. **Listicles with semantic structure** — `<ol>` with descriptive items (not bare sentences).
3. **Comparison tables** — `<table>` with explicit row/column headers.
4. **FAQs as standalone Q&A pairs** — CrackCMS emits FAQPage JSON-LD on every exam pillar.
5. **Definitions-as-paragraphs** — top-of-page paragraph defining the entity.

---

## 5. GEO-Friendly Search Snippet Targets

Per-pillar "definition paragraph" patterns:

> *UPSC CMS (Combined Medical Services Examination) is an annual recruitment exam conducted by the Union Public Service Commission for Medical Officers in Central Government services. The exam has two papers of 120 questions each, totalling 240 questions with 0.33 negative marking per wrong answer. General category cutoff for 2024 was ~320/960.*

This 60-90 word paragraph: appears on `/cms`, is the first paragraph in HTML, has the canonical name in bold, embeds two facts (240, 0.33) and a specific number (320/960). All retrievers can cite this verbatim.

All 7 exam pillars follow this pattern.

---

## 6. Avoiding GEO Failure Modes

| Failure mode | Fix |
|---|---|
| LLM hallucinates cutoff numbers | Stable, year-tagged cutoff data + cross-year consistency. |
| LLM pulls outdated eligibility | `dateModified` + visible "Last reviewed" stamps. |
| LLM cites the wrong organization as source | Explicit `publisher` JSON-LD across all guide and exam pages. |
| LLM author confusion | Reviewer profile pages (pending) → unique entity per reviewer. |
| LLM cites a third party, not CrackCMS | Digital-PR + backlink earning strategy (see SEO_MASTER_PLAN.md §5). |

---

## 7. Specific LLM Surfaces

### ChatGPT / OpenAI
- GPTBot retrievable. Allow-listed in robots.
- Citation: prefer recent pages with `Article` schema + author.

### Perplexity
- Heavy on UpToDate-style citations. Trustworthy attribution matters.

### Gemini / Google AI Mode
- Inherits Google's index. Same EEAT + AEO tactics apply.
- Google-Extended bot allowed.

### Claude / Anthropic
- ClaudeBot + Claude-Web allowed.
- Citation-friendly when page is fact-rich + has author + review date.

### Microsoft Copilot
- Often uses Bing index. Bingbot allowed.
- Bing Webmaster Tools submit sitemap.

---

## 8. Cracking Multi-Source Consensus

LLMs answer a question only if **multiple sources agree**. Tactics:
- Every UPSC CMS fact (cutoff, topper, pattern) is sourced from official PDFs.
- Definitions should appear identically across exam pillar / guide / year pages.
- `sameAs` across `Organization` schema links to GitHub + social + Crunchbase if available.
- Stickiness: same product name, same taglines across pages.

---

## 9. GEO Audit Checklist

For every public page:
- [x] Has unique title + description.
- [x] Has entity-rich opening paragraph.
- [x] Has structured data (Course / Article / FAQ).
- [x] Has visible author or publisher.
- [x] Has visible lastReviewed date.
- [x] Contains at least one comparative or enumerative element (table/list).
- [x] Outbound links to authoritative .gov.in / .edu / .org sources.

---

## 10. Pre-Cited Sources

Pages should also link to:
- `https://www.who.int/` (WHO guidelines)
- `https://www.icmr.gov.in/` (Indian Council of Medical Research)
- `https://www.iapindia.org/` (Indian Academy of Pediatrics)
- `https://www.iaph.org/` (Indian Association for Parenteral & Enteral Nutrition)
- `https://www.ima-india.org/` (Indian Medical Association)

These are sprinkled into current exam pages in the "Books" section. Phase 3 should formalise them into a "Sources" block at the top of every exam pillar.

---

## 11. Summary

CrackCMS is structurally well-prepared for GEO because:
- Robust `Organization` + `WebSite` + `Course` schema already in place.
- AI crawlers explicitly allowed.
- Author + reviewer + date stamps already on guide pages.
- Self-contained entity paragraphs at the top of every pillar.

Most of the remaining work is content-quality and backlink authority — that's the digital-PR + outreach engine covered in `SEO_MASTER_PLAN.md`.
