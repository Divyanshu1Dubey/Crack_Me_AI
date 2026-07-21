# Content Roadmap — CrackCMS

> Prioritized publishing plan. All content is mapped to a search intent, a target keyword cluster, and an E-E-A-T signal. Roll-out cadence is once-per-week for top-tier guides and twice-per-week for supporting content.

---

## 1. Topical Clusters Owned by CrackCMS

| Cluster | Pillars | Supporting topics |
|---|---|---|
| **UPSC CMS** | `/cms` | Pattern, syllabus (Paper I/II), cutoff by year, toppers, books, preparation strategy, eligibility, salary, mock tests |
| **NEET PG** | `/neet-pg` | Same |
| **INI-CET** | `/ini-cet` | Same |
| **FMGE** | `/fmge` | FMGE vs NEXT, Indian-context pharmacology, internship rules |
| **USMLE** | `/usmle` | IMG-specific resources, ECFMG certification, residency match |
| **Medical Officer Jobs** | `/medical-officer`, `/government-doctor-jobs` | Per-state (UP/MP/Rajasthan/etc.), per-body (UPSC CMS, AIIMS MO, ESIC IMO, NHM, Railways, Defence) |
| **AI in Medical Education** | `/guides/ai-in-medical-education` | AI tutors, RAG vs vanilla LLM, hallucination risk, current state of evidence |

---

## 2. Priority Publishing Queue (Next 90 days)

### Phase 1 (Weeks 1-4): ship what already has a template

**Per year, per exam — programmatic (already shipped)**:
- `/cms/pyq/2020` through `/cms/pyq/2024` (5 pages done).
- `/neet-pg/pyq/2020` through `/neet-pg/pyq/2024` (Phase 2).
- `/ini-cet/pyq/january-2024`, `july-2024` (Phase 2).

**Guide catalogue** —already shipped:
- UPSC CMS, NEET PG, INI-CET, FMGE, USMLE, Medical Officer Jobs, AI in Med-Ed, Study Plan Builder.

**New guides to add**:
- `/guides/cms-last-week-revision` — high-intent, low competition.
- `/guides/park-psm-high-yield-chapters` — links to textbook vendor.
- `/guides/first-aid-for-step-1-study-plan`.
- `/guides/medicine-pg-pyq-trends`.
- `/guides/government-doctor-jobs-after-mbbs`.

### Phase 2 (Weeks 5-8): state + cutoffs + subject

**State-specific MO pages** (8-12 states, highest search volume): UP, MP, Rajasthan, Maharashtra, Bihar, Tamil Nadu, Karnataka, West Bengal.

**Cutoff pages**: `/cms/cutoff/[year]` for 5 years; `/neet-pg/cutoff/[year]` for 5 years; `/ini-cet/cutoff/[year]/[institute]`.

**Subject PYQ pages**: `/cms/subject/[slug]` for top 12 subjects (Medicine, Surgery, Paediatrics, OBG, PSM, Pharmacology, Pathology, Microbiology, Anaesthesia, Ophthalmology, ENT, Orthopaedics).

### Phase 3 (Weeks 9-12): AI-Overview eligible content

These target "what is" + "how to" + comparison queries that AI assistants retrieve:
- `/cms/vs-ini-cet` — comparison
- `/cms/after-mbbs-best-career-options` — comparison shopping
- `/neet-pg/vs-usmle` — IMG comparison
- `/usmle/vs-next` — Indian NEXT vs USMLE
- `/fmge/vs-next` — Indian licensing path
- `/guides/best-medical-books-mbbs`

---

## 3. Per-Cluster Content Plan

### UPSC CMS cluster
**Keyword universe (top 30, monthly volume estimates from realistic India-centric GSC patterns):**
- "UPSC CMS previous year question paper" (40k)
- "UPSC CMS syllabus" (35k)
- "UPSC CMS eligibility" (8k)
- "UPSC CMS salary" (6k)
- "UPSC CMS cutoff" (5k)
- "UPSC CMS mock test free" (4k)
- "UPSC CMS books" (3.5k)
- "UPSC CMS 2024" + year (high seasonal)
- "UPSC CMS preparation strategy" (1.5k)
- "UPSC CMS question paper with answers" (1.2k)
- "UPSC CMS result" + year (1k)

**Page mesh:**
- Hero `/cms` covers pattern + eligibility + books + syllabus + FAQs.
- Hub `/cms/pyq` indexes year pages.
- Year `/cms/pyq/[year]` discusses subject distribution + cutoff + toppers + per-year trends + AI tutor demo.
- Subject pages `/cms/subject/[slug]` show subject-level analytics.
- Comparison pages `/cms/vs-ini-cet`, `/cms/vs-neet-pg`.
- Cutoff pages `/cms/cutoff/[year]`.

### NEET PG cluster
Same template, with `/neet-pg`, `/neet-pg/pyq/[year]`, `/neet-pg/subject/[slug]`.

### INI-CET cluster
Sessions (Jan / July) drive year keys: `/ini-cet/pyq/[session]` where session = `january-2024`, `july-2024`, etc.

### FMGE cluster
Two-year arc: `/fmge/december-2024`, `/fmge/june-2025`.

### USMLE cluster
Step 1 / Step 2 are the sub-pillars: `/usmle/step-1`, `/usmle/step-2-ck`.

### Medical Officer / Gov Jobs cluster
State pages (UPPSC, MPPSC, etc.), employer pages (ESIC IMO, NHM, AIIMS MO, Railways, Defence).

---

## 4. Content Quality Standards

Every published piece must satisfy the EEAT bar:
1. **Author byline** with credential (MBBS / MD / MS / BDS / etc.).
2. **Reviewer byline** with credential (MD / MS in the topic; 5+ years experience).
3. **Last reviewed** timestamp visible to user.
4. **Sources** tier-1 (UPSC, NBE, AIIMS, NMC, USMLE) + tier-2 (textbooks).
5. **Conflict-of-interest** disclosure.
6. **Update cadence** visible to user (12-monthly; updates logged in Changelog).

Length targets:
- Topical pillars: 1,800-2,500 words.
- Long-form guides: 2,500-4,000 words.
- Year / state pages: 600-1,200 words (unique per page).
- Subject pages: 800-1,500 words.

---

## 5. Refresh Cadence

| Asset | Refresh cadence | Trigger |
|---|---|---|
| Year PYQ page | Within 7 days of new UPSC notification | New result PDF |
| Subject PYQ page | Quarterly | New data on subject trends |
| Guide | Annually | New edition / new pattern |
| State MO page | Monthly | New vacancy notification |
| Cutoff page | Annually | New result |

Each refresh must update the visible `lastReviewed` timestamp. Drift longer than 6 months should be flagged.

---

## 6. Distribution & Promotion

Every new piece is:
- Pushed to the platform's news dashboard `/trends` if relevant.
- Linked from `<Footer>` if high-tier.
- Cross-linked from at least 3 contextual pages (see `INTERNAL_LINKING_REPORT.md`).
- Pushed to subscribers (Razorpay-paying users + Telegram channel).
- Pitched via digital-PR list (see `SEO_MASTER_PLAN.md` §5).
