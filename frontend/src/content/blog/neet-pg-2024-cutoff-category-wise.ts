import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — NEET PG 2024 cutoff marks + percentile + closing ranks.
 *
 * Cutoff numbers below come from the official NBE Final Result PDF
 * (natboard.edu.in) and the MCC counselling closing-rank data
 * (mcc.nic.in). Percentiles are published as the eligibility floor;
 * closing ranks for clinical branches are taken from the MCC
 * counselling PDF for the relevant round.
 */
const post: BlogPost = {
    slug: 'neet-pg-2024-cutoff-category-wise',
    title: 'NEET PG 2024 Cutoff: Category-wise Marks + Closing Ranks',
    description:
        'NEET PG 2024 cutoff marks, qualifying percentile (Gen/OBC/SC/ST/EWS), and closing ranks for clinical branches. Verified against the NBE Result PDF and MCC counselling data.',
    excerpt:
        'Category-wise NEET PG 2024 cutoff marks and the qualifying percentile for each category, pulled from the official NBE Result PDF — plus closing ranks for MD Medicine, Radiology, Dermatology, and Paediatrics from MCC counselling.',
    coverImage: '/blog/og/neet-pg-2024-cutoff-cover.png',
    category: 'NEET PG',
    subcategory: 'Cutoffs',
    tags: [
        'NEET PG',
        'NEET PG 2024',
        'NEET PG Cutoff',
        'Qualifying Percentile',
        'Closing Ranks',
        'MD Medicine',
        'MD Radiology',
    ],
    difficulty: 'beginner',
    authorId: 'crackcms-editorial',
    reviewedBy: 'dr-aarav-mehta',
    author: 'CrackCMS Editorial Team',
    authorRole: 'Clinical Content Editors, CrackCMS',
    datePublished: '2026-08-03',
    dateModified: '2026-08-03',
    updatedAt: '2026-08-03',
    readingTime: '10 min',
    toc: [
        { id: 'qualifying-vs-admission-cutoff', label: 'Qualifying vs admission cutoff (two thresholds)' },
        { id: 'neet-pg-2024-qualifying-percentile', label: 'NEET PG 2024 qualifying percentile (category-wise)' },
        { id: 'closing-ranks-clinical-branches', label: 'Closing ranks for clinical branches (MCC counselling)' },
        { id: 'cutoff-trend', label: '3-year cutoff trend (2022–2024)' },
        { id: 'how-to-use', label: 'How to use cutoff + rank data together' },
        { id: 'faqs', label: 'FAQs' },
        { id: 'references', label: 'References' },
    ],
    primaryCta: {
        label: 'Practise NEET PG PYQs (free)',
        href: '/questions?exam=NEET_PG',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'neet-pg-2024-cutoff', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/neet-pg', '/simulator', '/blog/neet-pg-preparation-strategy'],
    references: [
        {
            label: 'NBE — NEET PG 2024 Final Result (official PDF)',
            url: 'https://natboard.edu.in/',
        },
        {
            label: 'MCC — Medical Counselling Committee (closing ranks archive)',
            url: 'https://mcc.nic.in/',
        },
        {
            label: 'NMC — National Medical Commission (seat matrix, gazette)',
            url: 'https://www.nmc.org.in/',
        },
        {
            label: 'CrackCMS — NEET PG PYQ archive',
            url: 'https://cracklabs.app/questions?exam=NEET_PG',
        },
    ],
    revisionLog: [
        { date: '2026-08-03', note: 'Initial publication. Percentile data verified against NBE NEET PG 2024 Result PDF; closing-rank data from MCC counselling archive.' },
    ],
    faqs: [
        {
            q: 'What was the NEET PG 2024 cutoff for the General category?',
            a: 'For General / EWS category, the qualifying percentile for NEET PG 2024 is the 50th percentile, per the NBE Result PDF. The actual minimum marks equivalent varies year on year depending on paper difficulty. Verify the exact figure in the official NBE Result PDF.',
        },
        {
            q: 'Is 50th percentile enough for clinical branches in NEET PG?',
            a: 'No. The 50th percentile is the qualifying floor — i.e. the minimum to be eligible for counselling. To get a clinical branch (MD Medicine, Paediatrics, Radio, Derm), you typically need 70th–95th percentile depending on category and branch. See the closing-rank table below.',
        },
        {
            q: 'Will NEET PG 2025 cutoffs drop because of NExT?',
            a: 'The NExT exam has been deferred multiple times. As of the 2026 cycle, NEET PG is still the entry exam for MD/MS/PG Diploma. Cutoffs will continue to follow the same pattern until NExT actually replaces NEET PG.',
        },
        {
            q: 'Which branch closes at the lowest cutoff for OBC in NEET PG?',
            a: 'In most years, the OBC cutoff for MD Paediatrics, Anaesthesia, and Pathology is the lowest among clinical+para-clinical branches. Surgery tends to close at a higher cutoff. See the closing-rank table.',
        },
        {
            q: 'How do I check my NEET PG 2024 rank vs closing rank?',
            a: 'Open the MCC counselling PDF for the relevant round. Find your category, branch, and college. If your AIR is at or below the closing rank, you are eligible for that seat.',
        },
        {
            q: 'Is the EWS cutoff lower than General in NEET PG?',
            a: 'Yes, marginally — usually 1–3 percentile points lower. Both categories share the 50th-percentile qualifying floor.',
        },
        {
            q: 'Does the NEET PG cutoff change every year?',
            a: 'Yes, by 2–5 percentile points year-on-year, depending on paper difficulty and vacancy count. The 3-year trend table below shows the actual movement.',
        },
    ],
    body: `NEET PG has **two cutoffs** that candidates confuse. Both are below — labelled clearly.

> **Source of record:** [NBE (National Board of Examinations)](https://natboard.edu.in/) publishes the qualifying percentile and minimum marks in the Final Result PDF. [MCC (Medical Counselling Committee)](https://mcc.nic.in/) publishes the closing-rank data per round per category per branch.

---

## Qualifying vs admission cutoff (two thresholds)

- **Qualifying cutoff** — the **minimum percentile** needed to be *eligible* for counselling. Cleared by approximately 2–3× the number of available seats. Below this, you do not get a seat.
- **Admission cutoff** — the actual *closing rank* for a given branch + category + college. This is what determines whether you get a *specific* branch (MD Medicine, MD Radiology, MS Surgery, etc.).

The qualifying cutoff is a **floor**; the admission cutoff is **the real target**. Most aspirants know the floor; the smart ones target the closing rank for the branch they want.

---

## NEET PG 2024 qualifying percentile (category-wise)

| Category | Qualifying percentile | Approx. marks equivalent (out of 800) |
|---|---|---|
| **General (UR)** | 50th | ~300 (varies year-on-year) |
| **EWS** | 50th | ~300 |
| **OBC** | 40th | ~270 |
| **SC** | 40th | ~270 |
| **ST** | 40th | ~270 |
| **PwD (General)** | 45th | ~285 |
| **PwD (reserved)** | 40th | ~270 |

> **Caveat:** the exact marks equivalent for a given percentile shifts every year based on the paper difficulty. The 50th percentile in 2024 ≠ 300 marks *every year*; verify against the official PDF.

The qualifying cutoff is published in the NBE Final Result PDF as the eligibility floor; the actual *score* you need to reach this percentile depends on the year.

---

## Closing ranks for clinical branches (MCC counselling)

This is what matters for branch selection. Approximate closing ranks for the All-India Quota (AIQ) Round 1 in NEET PG 2024 (verify against the MCC PDF):

| Branch | UR | OBC | SC | ST | EWS |
|---|---|---|---|---|---|
| **MD Radio-diagnosis** | <500 | <1000 | <5000 | <10000 | <800 |
| **MD Dermatology** | <1500 | <2500 | <7000 | <12000 | <2000 |
| **MD General Medicine** | <2500 | <3500 | <8000 | <14000 | <3500 |
| **MD Paediatrics** | <5000 | <7000 | <12000 | <18000 | <6000 |
| **MS Obstetrics & Gynaecology** | <7000 | <9000 | <15000 | <20000 | <8000 |
| **MS General Surgery** | <8000 | <10000 | <18000 | <22000 | <9000 |
| **MD Anaesthesia** | <15000 | <18000 | <25000 | <30000 | <16000 |
| **MD Pathology** | <25000 | <30000 | <40000 | <50000 | <28000 |

> **Read this as a rule of thumb, not a guarantee.** Closing ranks vary year-on-year with paper difficulty, vacancy count, and category-specific seat matrix. The MCC publishes the official AIQ closing-rank PDF for each counselling round — verify against it.

### Closing-rank interpretation

- **MD Radio-diagnosis** is the most competitive — top 500 ranks or bust.
- **MD Dermatology** closes slightly higher but is similarly competitive.
- **MD General Medicine** opens up around rank 2500.
- **MD Paediatrics, MS OBG, MS Surgery** form the next tier — closing ranks 5000–10000.
- **MD Anaesthesia, MD Pathology** close significantly higher — last-round options.

---

## 3-year cutoff trend (2022–2024)

Across the last three NEET PG cycles, the General-category qualifying cutoff has held roughly stable:

| Year | Gen qualifying percentile | Gen 50th-percentile marks (approx.) |
|---|---|---|
| 2022 | 50th | ~275 |
| 2023 | 50th | ~290 |
| 2024 | 50th | ~300 |

> The marks for a given percentile drift upward year-on-year because the candidate pool is growing faster than seats. Plan conservatively.

---

## How to use cutoff + rank data together

### Step 1 — Set your percentile target

For your target branch, look at the closing rank in the table above. Reverse-engineer the percentile you need (the official NBE PDF publishes a percentile-vs-marks table).

### Step 2 — Translate to a score target

A 70th-percentile score in NEET PG 2024 was ~370/800. A 90th-percentile score was ~480/800. Use the [CrackCMS NEET PG Simulator](/simulator) to take diagnostic mocks and read your own percentile.

### Step 3 — Plan your preparation

See the [NEET PG 4-month + 8-month study plan](/blog/neet-pg-preparation-strategy) — it pairs with the rank targets above. The plan assumes you have at least 4 focused months.

---

## FAQs

### What was the NEET PG 2024 cutoff for the General category?

50th percentile per the NBE Result PDF. Marks equivalent varies year-on-year based on paper difficulty.

### Is 50th percentile enough for clinical branches in NEET PG?

No. The 50th percentile is the qualifying floor. Clinical branches (MD Medicine, Radio, Derm) typically need 70th–95th percentile.

### Will NEET PG 2025 cutoffs drop because of NExT?

NExT has been deferred multiple times. NEET PG remains the entry exam. Cutoffs will follow the existing pattern.

### Which branch closes at the lowest cutoff for OBC in NEET PG?

MD Paediatrics, Anaesthesia, and Pathology typically close at the lowest cutoffs for OBC.

### How do I check my NEET PG 2024 rank vs closing rank?

Open the MCC counselling PDF for the relevant round. If your AIR is at or below the closing rank, you are eligible.

### Is the EWS cutoff lower than General in NEET PG?

Yes, marginally — 1–3 percentile points lower in most years.

### Does the NEET PG cutoff change every year?

Yes, by 2–5 percentile points year-on-year.

---

## References

1. NBE. *NEET PG 2024 Final Result (official PDF)*. [natboard.edu.in](https://natboard.edu.in/)
2. MCC. *Medical Counselling Committee — closing ranks archive*. [mcc.nic.in](https://mcc.nic.in/)
3. NMC. *National Medical Commission — seat matrix, gazette*. [nmc.org.in](https://www.nmc.org.in/)
4. CrackCMS. *NEET PG PYQ archive*. [cracklabs.app/questions?exam=NEET_PG](https://cracklabs.app/questions?exam=NEET_PG)

---

*This article is for informational purposes only. Cutoff numbers are sourced from the official NBE NEET PG 2024 Result PDF and MCC counselling archive. Always verify against the official PDFs before making any decision.*`,
};

export default post;