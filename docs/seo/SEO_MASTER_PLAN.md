# SEO Master Plan — CrackCMS

> Mission: Make CrackCMS the most-authoritative medical exam preparation platform on the open web, ranking #1 across UPSC CMS, NEET PG, INI-CET, FMGE, USMLE, and Medical Officer recruitment.

**Document version:** v1.0 (July 2026) — derived from live site audit, competitive analysis, and ranking-factor study.

---

## 1. Mission, KPIs, and Time Horizons

### KPIs (12-month horizon)

| KPI | Baseline (today) | Target | Notes |
|---|---|---|---|
| Organic clicks / month (Google Search Console) | unknown — measure | +300% | |
| Branded vs non-branded query mix | unknown | 60% non-branded | Indicates topical authority |
| Pages ranking top 10 (Ahrefs / GSC) | unknown | 200+ | Across the 7 priority keyword clusters |
| Domain Rating (Ahrefs) | unknown | 35+ | Earned through quality content + digital PR |
| Referring domains | unknown | 200+ | From white-hat outreach |
| Mentions in LLM answers (Perplexity / ChatGPT) | unknown | Trackable via prompt trackers |

### Horizons
- **30 days (technical / on-page):** ship all items in `TECHNICAL_SEO_AUDIT.md`, complete EEAT pages, deploy schema, expand sitemap.
- **60–90 days (content):** ship the high-priority topical clusters from `CONTENT_ROADMAP.md` — ~20 new content pieces per exam pillar.
- **90–180 days (authority):** execute the `INTERNAL_LINKING_REPORT.md` hub-and-spoke plan, begin digital PR via `COMPETITOR_GAP_ANALYSIS.md`.
- **180–365 days (off-page):** roll out backlink earning strategy; track mentions and links via Ahrefs.

---

## 2. Pillars and Topical Authority

CrackCMS wins by owning seven **pillar keywords** deeply. Each pillar gets a canonical `/<exam>` page (already built) plus programmatic hubs (`/<exam>/pyq`, `/<exam>/subject`, `/<exam>/cutoff`, etc.) and supporting `Article`/`FAQPage` schema.

| Pillar | Primary search intent | Hero page | Sub-pages to ship |
|---|---|---|---|
| **UPSC CMS** | Informational + transactional | `/cms` | `/cms/pyq`, `/cms/pyq/[year]`, `/cms/subject/[slug]`, `/cms/cutoff/[year]`, `/cms/books`, `/cms/syllabus`, `/cms/preparation`, `/cms/salary`, `/cms/eligibility` |
| **NEET PG** | Informational + transactional | `/neet-pg` | Same structure as CMS |
| **INI-CET** | Informational | `/ini-cet` | Same structure |
| **FMGE** | Informational | `/fmge` | Same structure |
| **USMLE** | Informational | `/usmle` | Same structure |
| **Medical Officer Jobs** | Transactional | `/government-doctor-jobs` | Sub-pages per state (UP, MP, Rajasthan, etc.) — uses real `jobs.Job` data |
| **Government Doctor Jobs** | Transactional | `/government-doctor-jobs` | Same |

### E-E-A-T coverage required
Every pillar page must surface:
- **Author** (with credential + medical-college page).
- **Reviewer** (clinician MBBS + MD/MS, 5+ years experience).
- **Last reviewed** timestamp visible to user.
- **Sources** (Tier 1 = conducting-body notifications, Tier 2 = standard textbooks).
- **Conflict of interest** disclosure (already exists on `editorial-policy`).

---

## 3. Schema.org Playbook

The site already emits Organization, WebSite, FAQPage, Course, BreadcrumbList, SoftwareApplication globally. Per-page schema strategy:

| Page type | Schema.org type(s) | Why |
|---|---|---|
| Landing (`/`) | Organization + WebSite + SoftwareApplication + FAQPage + BreadcrumbList | Site links, brand logo, FAQ rich result |
| Exam pillar (`/<exam>`) | Course + FAQPage + BreadcrumbList | Course card + FAQ rich result |
| Guide (`/guides/<slug>`) | Article + FAQPage + BreadcrumbList | Top stories carousels, FAQ |
| Year PYQ (`/<exam>/pyq/[year]`) | Article + FAQPage + BreadcrumbList | Topical authority, FAQ |
| Job portal (`/jobs`) | JobPosting (one per listing) | Job rich result (defer — gated route) |
| About | AboutPage + Organization | Author/entity rich result |
| Legal pages | TermsOfService / PrivacyPolicy / MedicalWebPage | Compliance + EEAT |

**Validate continuously**: build a CI step that runs Google's Rich Results Test API on every changed route (deferred — manual validation post-deploy).

---

## 4. Internal Linking Architecture

Hub-and-spoke:

```
                          ROOT (/)
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
       /cms             /neet-pg          /guides (hub)
        │                 │                 │
   /cms/pyq            /neet-pg/pyq      /guides/upsc-cms...
   /cms/books          /neet-pg/books
   ...                 ...
```

Every exam page MUST link:
1. Back to its **landing exam** page.
2. To the **PYQ hub** for that exam.
3. To the **guides hub** with a relevant guide.
4. To the **jobs hub** if related.
5. To the **about + contact + privacy** trust set.

The `<Footer>` already implements this for the site-wide graph. The per-page guides + exam pages need **contextual in-content links** — see `INTERNAL_LINKING_REPORT.md`.

---

## 5. Backlink Earning Strategy (White-Hat Only)

> **Important constraint:** Google's Webmaster Guidelines explicitly prohibit link buying, link exchanges, PBNs, scraper sites, and link farms. Any of these may yield short-term gains but ultimately produce manual actions. The plan below only uses tactics compliant with Google's guidelines.

### 1. Digital PR / HARO / Source Quoted
- Sign up for HARO (Help A Reporter Out), SourceBottle, Qwoted, Terkel.
- 2-minute daily scan for medical-education queries.
- Target outlets: *Indian Express Health*, *Forbes India Healthcare*, *Medical Dialogues*, *Hindustan Times Health*, *Times of India — Health section*.
- Track responses + placements in a simple spreadsheet.

### 2. Guest posts on real editorial sites
- Pitch 4-6 actionable topics to medical publications:
  - *Plethy Magazine*, *MedBound Times*, *Express Healthcare*, *Healthcare Radius*.
- Target Domain Rating 30+ Indian medical publications.
- Anchor text: branded (CrackCMS, CrackLabs) or natural ("medical prep platform").

### 3. Educational resource pages
- Pitch to medical-college official portals, university placement cells, doctors' associations (IMA, API, IAP, FOGSI) for inclusion in their student resources.

### 4. Original data / research reports
- Publish quarterly "Indian Medical Exam Trends" reports using anonymised aggregate platform data (pass-rate by subject, drop-out topics).
- Pitch to medical education outlets + bloggers.

### 5. Tool / calculator pages
- Build free embeddable tools: NEET PG AIR predictor, INI-CET cutoff calculator, USMLE Step 2 score estimator.
- These earn natural links when other prep sites embed them via iframe.

### 6. Reddit / Telegram / Quora (community-led)
- Provide genuine expert answers in r/IndianMedicalStudents, r/UPSC, r/NEETPG, r/MBBS.
- Never spam — link only when it adds value.
- Build a curated Telegram study channel (organic growth, not paid promotion).

---

## 6. Measurement and Reporting Cadence

| Cadence | What we report |
|---|---|
| **Weekly** | GSC: top queries, pages, CTR. Noteworthy rank movements. Indexing coverage. |
| **Bi-weekly** | New content shipped; schema validation results. New backlinks acquired. |
| **Monthly** | Full SEO dashboard: traffic, conversions, ranking movement, share of voice. Drift from KPIs. |
| **Quarterly** | Refresh the content roadmap; expire under-performing pages; identify new long-tail opportunities. |

---

## 7. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| AI-generated content flagged by Google's March 2024+ helpful content systems | Medium | High | Every AI draft goes through a clinician reviewer before publish. Citations visible. |
| Backlink spikes from low-quality directories | Medium | High | Disavow file reviewed monthly; outreach restricted to DR 30+ editorial sites. |
| Subject reclassification by UPSC / NBE breaking indexed URLs | Low | Medium | Use slug names ("upsc-cms", not "medical-officer-prelims"). 410 retired routes. |
| Thin programmatic pages get indexed | Medium | Medium | Every programmatic page has 600+ unique words. |
| RAG hallucinations get cited in AI answers | Medium | High | Medical-review policy + quarterly red-team audits (already documented). |

---

## 8. Next 90 Days — Concrete Ship List

1. **All required reports** in `docs/seo/` (this directory) — DONE after this commit.
2. **Programmatic PYQ pages** for UPSC CMS 2020-2024 (5 years) — DONE after this commit.
3. **Per-page metadata** for all 40+ public routes — DONE after this commit.
4. **Internal linking pass** across exam pillar pages — see `INTERNAL_LINKING_REPORT.md`.
5. **Subject-wise PYQ pages** under `/cms/subject/[slug]` and similar for NEET PG — Phase 2.
6. **State MO pages** at `/government-doctor-jobs/[state]` — Phase 2.
7. **Cutoff pages** at `/cms/cutoff/[year]` — Phase 2.
8. **Embeddable AIR predictor** widget — Phase 2 (linkable asset).
9. **First quarterly "Medical Exam Trends" report** — Phase 2.
10. **Digital PR outreach** — Phase 2.
