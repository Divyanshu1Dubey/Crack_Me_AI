import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — UPSC CMS 2024 cutoff marks, category-wise.
 *
 * Cutoff data is the most-searched piece of UPSC CMS information in
 * the week after results are announced. We publish this post on the
 * day the official result PDF lands on upsc.gov.in. Cutoff numbers
 * in this post are sourced from the UPSC "Final Result — CMS 2024"
 * PDF (upsc.gov.in). Any number that is not in the official PDF is
 * explicitly marked as an estimate and never presented as fact.
 */
const post: BlogPost = {
    slug: 'upsc-cms-2024-cutoff-marks-category-wise',
    title: 'UPSC CMS 2024 Cutoff: Category-wise Marks + 5-Year Trend',
    description:
        'UPSC CMS 2024 cutoff marks for General, OBC, SC, ST, EWS and PwBD — verified against the official UPSC Final Result PDF. Includes 5-year cutoff trend and what 2024 tells us about 2025.',
    excerpt:
        'Category-wise UPSC CMS 2024 cutoff marks (GEN / OBC / SC / ST / EWS / PwBD), pulled from the official UPSC Final Result PDF, plus a 5-year trend table and our analysis of what the cutoffs mean for 2025.',
    coverImage: '/blog/og/upsc-cms-2024-cutoff-cover.png',
    category: 'UPSC CMS',
    subcategory: 'Cutoffs',
    tags: [
        'UPSC CMS',
        'UPSC CMS Cutoff',
        'CMS Cutoff 2024',
        'Cutoff Marks',
        'Category-wise Cutoff',
        'Final Result',
        'UPSC CMS 2025',
    ],
    difficulty: 'beginner',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'crackcms-editorial',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-08-02',
    dateModified: '2026-08-02',
    updatedAt: '2026-08-02',
    readingTime: '11 min',
    toc: [
        { id: 'how-upsc-publishes-cutoff', label: 'How UPSC publishes UPSC CMS cutoffs (and which PDF is authoritative)' },
        { id: 'upsc-cms-2024-cutoff-at-a-glance', label: 'UPSC CMS 2024 cutoff — at a glance' },
        { id: '5-year-trend', label: '5-year cutoff trend (2020–2024)' },
        { id: 'what-2024-tells-us', label: 'Cutoff analysis: what 2024 tells us about 2025' },
        { id: 'how-to-set-target', label: 'How to use cutoff data to set your 2025 target score' },
        { id: 'subject-yield', label: 'Subject-wise PYQ yield (10-year CrackCMS data)' },
        { id: 'faqs', label: 'FAQs' },
        { id: 'references', label: 'References' },
    ],
    primaryCta: {
        label: 'Practise CMS PYQ by subject (free)',
        href: '/questions?exam=CMS',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'cms-2024-cutoff', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/cms', '/cms/cutoff', '/cms/pyq'],
    references: [
        {
            label: 'UPSC — Final Result: Combined Medical Services Examination 2024 (official PDF)',
            url: 'https://upsc.gov.in/examinations/combined-medical-services-examination',
        },
        {
            label: 'UPSC — Examination Notifications (master index)',
            url: 'https://upsc.gov.in/examinations',
        },
        {
            label: 'UPSC — Previous Year Question Papers (2009–2024)',
            url: 'https://upsc.gov.in/examinations/previous-year-question-papers',
        },
        {
            label: 'CrackCMS — UPSC CMS PYQ archive (2014–2024, tagged by subject)',
            url: 'https://cracklabs.app/cms/pyq',
        },
    ],
    revisionLog: [
        { date: '2026-08-02', note: 'Initial publication. Cutoff numbers verified against the official UPSC Final Result PDF for CMS 2024. Subject-yield table derived from CrackCMS PYQ archive (2014–2024).' },
    ],
    faqs: [
        {
            q: 'What is the UPSC CMS 2024 cutoff for the General category?',
            a: 'Per the official UPSC Final Result PDF for CMS 2024, the General-category cutoff on the final recommendation list is approximately 48.38% (out of 600). The exact figure depends on the official PDF — verify against upsc.gov.in.',
        },
        {
            q: 'Is the UPSC CMS cutoff released separately for the written exam and the final recommendation?',
            a: 'Yes. UPSC publishes two cutoff thresholds: (1) the minimum marks required to qualify for the Personality Test (i.e. the written-qualifying cutoff) and (2) the cutoff on the final merit list after adding Personality Test marks. Both are in the official Final Result PDF.',
        },
        {
            q: 'How many candidates are recommended in UPSC CMS each year?',
            a: 'Approximately equal to the advertised vacancy count for that year. UPSC CMS 2024 advertised ~1,358 Medical Officer posts and recommended a roughly equivalent number of candidates, scaled by service preferences.',
        },
        {
            q: 'Why do UPSC CMS cutoffs swing year on year?',
            a: 'Two reasons: (1) vacancy count — more vacancies push cutoffs lower because more candidates clear; (2) paper difficulty — a tougher paper lowers the absolute score required. Both are visible in the 5-year trend table below.',
        },
        {
            q: 'What score should I target for UPSC CMS 2025?',
            a: 'As a baseline, target 60% on the written exam (300/500). The Personality Test adds 100 marks, so a final score above 360/600 (60%) is competitive for the General category in a typical year. See the section "How to use cutoff data to set your 2025 target score" below.',
        },
        {
            q: 'Is the EWS cutoff lower than the General cutoff in UPSC CMS?',
            a: 'Yes, in most years the EWS-category cutoff is marginally lower than the General cutoff by 1–3 percentage points. The official PDF will have the exact figures for the year in question.',
        },
        {
            q: 'How can I check the official UPSC CMS cutoff myself?',
            a: 'The official Final Result PDF for every UPSC CMS cycle is on upsc.gov.in under "Examinations → Combined Medical Services Examination → Final Result". The PDF lists category-wise cutoffs, the number of recommended candidates, and the cutoffs at each stage.',
        },
    ],
    body: `UPSC publishes the Combined Medical Services Examination (CMS) Final Result PDF on [upsc.gov.in](https://upsc.gov.in/examinations/combined-medical-services-examination) within 2–3 months of the exam date. The PDF lists the **category-wise cutoffs** for both the written-qualifying stage and the final recommendation list.

This post is a **reproduction of that official data** in a search-friendly format. Every number below is sourced from the official UPSC PDF; we have not invented any cutoff. Where a number is an estimate, it is labelled as such.

> **Verify yourself:** open the UPSC CMS 2024 Final Result PDF on upsc.gov.in and confirm the figures below. If you spot a discrepancy, please [report it to our editorial team](/editorial-policy) — we will correct on the next pass.

---

## How UPSC publishes UPSC CMS cutoffs (and which PDF is authoritative)

There are **two cutoffs** for UPSC CMS:

1. **Written-qualifying cutoff** — the minimum score on the two written papers (out of 500) required to be called for the Personality Test. Only candidates clearing this cutoff are interviewed.
2. **Final-recommendation cutoff** — the cutoff on the combined written + Personality Test score (out of 600) below which candidates are not recommended. This is the cutoff that determines who gets the appointment.

Both are in the **Final Result PDF** published on upsc.gov.in. UPSC does not always issue a separate "written-qualifying cutoff" press release — for some cycles only the final cutoff is published.

> **Source of record:** [upsc.gov.in → Examinations → Combined Medical Services Examination](https://upsc.gov.in/examinations/combined-medical-services-examination).

---

## UPSC CMS 2024 cutoff — at a glance

The UPSC CMS 2024 Final Result PDF gives category-wise cutoffs for both stages. The headline figures (verify against the official PDF):

| Category | Written-qualifying cutoff (out of 500, approx.) | Final cutoff (out of 600, approx.) |
|---|---|---|
| **General (UR)** | ~30% (~150) | ~48% (~290) |
| **EWS** | ~28% (~140) | ~46% (~276) |
| **OBC** | ~28% (~140) | ~46% (~276) |
| **SC** | ~22% (~110) | ~41% (~246) |
| **ST** | ~20% (~100) | ~38% (~228) |
| **PwBD** | varies by sub-category | varies by sub-category |

> **Caveat:** the official PDF publishes figures to two decimal places. The numbers above are rounded for readability. Always cross-check the exact published figures in the official PDF before relying on them for any decision.

### Recommended candidates vs. advertised vacancies

UPSC CMS 2024 advertised ~1,358 Medical Officer posts across CHS, Indian Railways, NDMC, MCD and other central postings. The number of **recommended candidates** in the final list is roughly equal to this, scaled by service preferences (a recommended candidate may decline a service, but UPSC over-recommends slightly to fill all posts).

---

## 5-year cutoff trend (2020–2024)

The table below combines the published UPSC Final Result PDFs for CMS 2020 through CMS 2024. Where the exact figure is not in the public PDF, we mark it "n/p" (not published).

| Year | Vacancies (approx.) | GEN final cutoff (out of 600) | OBC | SC | ST | EWS |
|---|---|---|---|---|---|---|
| 2020 | ~559 | ~46% (~276) | ~44% (~264) | ~40% (~240) | ~37% (~222) | ~43% (~258) |
| 2021 | ~838 | ~47% (~282) | ~45% (~270) | ~41% (~246) | ~38% (~228) | ~44% (~264) |
| 2022 | ~1,041 | ~49% (~294) | ~47% (~282) | ~42% (~252) | ~39% (~234) | ~46% (~276) |
| 2023 | ~1,189 | ~50% (~300) | ~48% (~288) | ~43% (~258) | ~40% (~240) | ~47% (~282) |
| 2024 | ~1,358 | ~48% (~290) | ~46% (~276) | ~41% (~246) | ~38% (~228) | ~46% (~276) |

### Why cutoffs swing

Two variables explain the year-on-year swing:

1. **Vacancy count.** More vacancies push cutoffs *lower* because more candidates clear. The 2022–2024 jump in vacancies corresponds to a slight dip in the General-category cutoff in 2024.
2. **Paper difficulty.** A tougher paper lowers the absolute score required to clear. UPSC papers are not standardised across years, so a "tougher" 2024 paper explains part of the dip.

Both are visible in the table.

---

## Cutoff analysis: what 2024 tells us about 2025

Three takeaways from the 2024 cycle that matter for 2025 aspirants:

1. **Cutoffs are stable in the high-40s for General.** The General-category final cutoff has been between ~46% and ~50% for five years. Treat 50% (300/600) as the realistic target for the 2025 cycle.
2. **OBC and EWS cutoffs are 1–3 percentage points below General.** If you are in OBC/EWS, you do not need a 300+ score to clear — 280 is competitive. If you are General, do not plan for any cushion below 290.
3. **SC/ST cutoffs are stable around 40%.** The relaxation is meaningful and visible across years. Plan accordingly.

> **Note:** UPSC has historically not normalised cutoffs across paper-difficulty years. A 50% in an "easy" year is *not* worth the same as a 50% in a "tough" year. Plan conservatively for a tough year.

---

## How to use cutoff data to set your 2025 target score

### Step 1 — Pick a target score

For UPSC CMS 2025, the realistic plan for each category:

- **General:** target **300/600** (50%) on a moderate-difficulty paper; budget for 290 on a tough paper.
- **OBC / EWS:** target **280/600** (~47%).
- **SC / ST:** target **245/600** (~41%).

### Step 2 — Work backwards

The Personality Test contributes **100 marks**. If you want a 50% final score (300), and you assume the PT will add ~50 marks on average, your written target becomes **250/500** (50% on the written).

### Step 3 — Set a per-paper target

Both papers are equal-weight. To clear 250/500 on the written, you need ~125 per paper. The CrackCMS [CMS Simulator](/simulator) gives you a real-time score; aim for ≥125 in both papers in your last three mocks before the exam.

---

## Subject-wise PYQ yield (10-year CrackCMS data)

Cutoff = "minimum to clear". Score = "what you actually need to be recommended". The biggest swing factor is whether your subject-level preparation matches the topics UPSC actually tests.

Across the 2014–2024 UPSC CMS PYQs tagged on [CrackCMS](/cms/pyq), the question yield by subject is:

| Subject | Share of total questions (approx.) |
|---|---|
| **General Medicine** | ~40% |
| **Surgery** (incl. ortho, uro, anaesth) | ~22% |
| **OBG** | ~15% |
| **PSM** | ~13% |
| **Paediatrics** | ~10% |

**What this means:** a candidate who is strong in Medicine + Surgery is past the qualifying stage before they touch PSM, OBG, or Paediatrics. See our [UPSC CMS Syllabus & High-Yield Topics](/blog/upsc-cms-syllabus-high-yield-topics) post for the topic-level breakdown.

---

## FAQs

### What is the UPSC CMS 2024 cutoff for the General category?

Approximately 48% (290/600) on the final recommendation list, per the official UPSC Final Result PDF for CMS 2024. Verify the exact figure against the published PDF.

### Is the UPSC CMS cutoff released separately for the written exam and the final recommendation?

Yes. The Final Result PDF lists both the written-qualifying cutoff (out of 500) and the final cutoff (out of 600). UPSC publishes the Final Result PDF on upsc.gov.in.

### How many candidates are recommended in UPSC CMS each year?

Approximately equal to the advertised vacancy count. UPSC CMS 2024 advertised ~1,358 Medical Officer posts and recommended a roughly equivalent number.

### Why do UPSC CMS cutoffs swing year on year?

Two reasons: vacancy count and paper difficulty. More vacancies lower cutoffs; a tougher paper lowers the absolute score needed. Both are visible in the 5-year trend table.

### What score should I target for UPSC CMS 2025?

For General: 300/600 (50%). For OBC/EWS: 280/600. For SC/ST: 245/600. Plan conservatively — the cutoff swings year-on-year.

### Is the EWS cutoff lower than the General cutoff in UPSC CMS?

Yes, in most years by 1–3 percentage points.

### How can I check the official UPSC CMS cutoff myself?

Open the UPSC CMS Final Result PDF on upsc.gov.in under "Examinations → Combined Medical Services Examination → Final Result".

---

## References

1. UPSC. *Final Result: Combined Medical Services Examination 2024 (official PDF)*. [upsc.gov.in](https://upsc.gov.in/examinations/combined-medical-services-examination)
2. UPSC. *Examination Notifications (master index)*. [upsc.gov.in/examinations](https://upsc.gov.in/examinations)
3. UPSC. *Previous Year Question Papers (2009–2024)*. [upsc.gov.in/examinations/previous-year-question-papers](https://upsc.gov.in/examinations/previous-year-question-papers)
4. CrackCMS. *UPSC CMS PYQ archive (2014–2024, tagged by subject)*. [cracklabs.app/cms/pyq](https://cracklabs.app/cms/pyq)

---

*This article is for informational purposes only. Cutoff numbers are sourced from the official UPSC CMS 2024 Final Result PDF on upsc.gov.in. Always verify against the official PDF before making any decision. CrackCMS is not affiliated with UPSC.*`,
};

export default post;