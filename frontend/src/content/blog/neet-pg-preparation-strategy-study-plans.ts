import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — NEET PG 4-month + 8-month preparation strategies.
 *
 * Companion piece to NEET PG 2024 cutoff. Covers two realistic plans
 * (4-month for graduate on the job, 8-month for final-year intern)
 * with daily schedule variants and subject triage.
 */
const post: BlogPost = {
    slug: 'neet-pg-preparation-strategy-study-plans',
    title: 'NEET PG Preparation: 4-Month & 8-Month Study Plans',
    description:
        'Two realistic NEET PG study plans — 4-month for working graduates, 8-month for interns. Daily schedule variants, subject triage, mock strategy, and high-yield resources.',
    excerpt:
        'Two realistic NEET PG study plans: 4-month for a working MBBS graduate, 8-month for a final-year intern. Both built around PYQs + subject triage + the CrackCMS Simulator.',
    coverImage: '/blog/og/neet-pg-prep-strategy-cover.png',
    category: 'NEET PG',
    subcategory: 'Strategy & Plans',
    tags: [
        'NEET PG',
        'NEET PG Preparation',
        'Study Plan',
        '4 Month Plan',
        '8 Month Plan',
        'Internship',
        'Working MBBS',
    ],
    difficulty: 'intermediate',
    authorId: 'crackcms-editorial',
    reviewedBy: 'dr-aarav-mehta',
    author: 'CrackCMS Editorial Team',
    authorRole: 'Clinical Content Editors, CrackCMS',
    datePublished: '2026-08-04',
    dateModified: '2026-08-04',
    updatedAt: '2026-08-04',
    readingTime: '12 min',
    toc: [
        { id: 'pattern-2026', label: 'NEET PG 2026 — pattern, syllabus, weightage at a glance' },
        { id: '8-month-plan', label: 'The 8-month plan (final-year intern)' },
        { id: '4-month-plan', label: 'The 4-month plan (working graduate)' },
        { id: 'daily-schedule', label: 'Daily schedule variants (3 / 5 / 8 hour)' },
        { id: 'high-yield-resources', label: 'High-yield resources' },
        { id: 'mock-strategy', label: 'Mock-test strategy on the CrackCMS Simulator' },
        { id: 'subject-triage', label: 'Subject triage — what to drop, what to deep-dive' },
        { id: 'faqs', label: 'FAQs' },
        { id: 'references', label: 'References' },
    ],
    primaryCta: {
        label: 'Start with the NEET PG Simulator',
        href: '/simulator',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'neet-pg-prep-strategy', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/neet-pg', '/simulator', '/blog/neet-pg-2024-cutoff-category-wise'],
    references: [
        {
            label: 'NBE — NEET PG information bulletin',
            url: 'https://natboard.edu.in/',
        },
        {
            label: 'NMC — Graduate Medical Education Regulations',
            url: 'https://www.nmc.org.in/',
        },
        {
            label: 'CrackCMS — NEET PG 2024 Cutoff (companion post)',
            url: 'https://cracklabs.app/blog/neet-pg-2024-cutoff-category-wise',
        },
    ],
    revisionLog: [
        { date: '2026-08-04', note: 'Initial publication. Aligned with NEET PG 2026 cycle.' },
    ],
    faqs: [
        {
            q: 'Is 4 months enough for NEET PG?',
            a: 'Yes, for an MBBS graduate who has been in clinical practice or active study. 4 months at 5–8 hours/day is sufficient. The constraint is intensity, not duration.',
        },
        {
            q: 'Should I solve subject tests or grand tests first?',
            a: 'Subject tests first. Two passes of subject tests, then two passes of grand tests. Grand tests on days 1 and 14 of every month; subject tests in between.',
        },
        {
            q: 'Is Marrow enough for NEET PG?',
            a: 'Marrow is enough for *content* but not for *PYQ integration*. The smartest path is to combine Marrow (or any video source) with the CrackCMS PYQ archive and Simulator.',
        },
        {
            q: 'When should I start revision?',
            a: 'Month 3 of the 8-month plan; Day 60 of the 4-month plan. Revision is half of the score — the first read is for coverage, the second is for retention.',
        },
        {
            q: 'Which subject should I drop to save time?',
            a: 'In the 4-month plan, drop Anatomy + Physiology deep-dives (cover only the high-yield Anatomy topics that recur in PYQs). In the 8-month plan, cover everything once but at lower depth on Biochemistry and Forensic Medicine.',
        },
        {
            q: 'How many NEET PG mocks should I take?',
            a: 'Minimum 20 full-length mocks before the exam. The first 5 should be diagnostic (no prep); the next 15 should be progressively under timed conditions with revision between.',
        },
        {
            q: 'Is coaching required for NEET PG?',
            a: 'No. Self-study + a strong PYQ bank + a reliable mock simulator can take you through. Coaching adds a structured schedule but is not mandatory.',
        },
    ],
    body: `NEET PG is a *specialist-entry* exam — the questions test both MBBS knowledge and clinical reasoning across 19 subjects. The syllabus is wider than UPSC CMS, the marks distribution is different, and the competition is sharper.

This post gives you **two realistic study plans** — 8 months (for final-year interns) and 4 months (for working graduates). Both end at the same place: a NEET PG score that is competitive for your target branch.

> **Read first:** the [NEET PG 2024 Cutoff](/blog/neet-pg-2024-cutoff-category-wise) post — it tells you what score you actually need.

---

## NEET PG 2026 — pattern, syllabus, weightage at a glance

| Item | Detail |
|---|---|
| **Mode** | Computer-Based Test (CBT) |
| **Duration** | 3.5 hours |
| **Questions** | 200 (out of 800 marks) |
| **Negative marking** | Yes — 1 mark deducted per wrong answer |
| **Subjects** | 19 (Pre-clinical: 3, Para-clinical: 4, Clinical: 12) |
| **Subject weightage** | Clinical subjects account for ~60% of marks |

The 19 subjects group into:

- **Pre-clinical** (Anatomy, Physiology, Biochemistry) — ~25% of marks
- **Para-clinical** (Pathology, Microbiology, Pharmacology, Forensic Medicine) — ~15% of marks
- **Clinical** (Medicine, Surgery, OBG, Paediatrics, Ortho, ENT, Ophth, Anaesthesia, Radio, Psych, Dermatology, Community Medicine) — ~60% of marks

> **Takeaway:** clinical subjects carry the majority of the score. Spend 60% of your prep time on clinical, even if it feels uncomfortable to deprioritise Anatomy.

---

## The 8-month plan (final-year intern)

### Month 1 — Pre-clinical + Pathology foundation

**Goal:** finish the *foundational* subjects that everything else rests on.

- Anatomy — only the high-yield topics (limbs, thorax, abdomen, head-and-neck). Skip microanatomy deep-dives.
- Physiology — system-by-system, with PYQs after every system.
- Biochemistry — focus on metabolism, vitamins, molecular biology. Skip pure chemistry.
- Pathology — General Pathology + Systemic Pathology (both Robbins-based).

### Month 2 — Para-clinical + Pharmacology

- Microbiology — high-yield: TB, HIV, malaria, hepatitis, hospital-acquired infections.
- Pharmacology — high-yield drug classes: antibiotics, anti-hypertensives, anti-diabetics, anti-epileptics, anti-psychotics.
- Forensic Medicine — cover the legal/medico-legal sections deeply; toxicology basics.

### Month 3 — Clinical subjects begin + first revision

- Medicine — Cardiology, Respiratory, GI, Endocrine (the high-yield four)
- Surgery — General surgery topics + ortho + anaesthesia basics
- **First PYQ revision pass** — solve CMS + NEET PG + INI-CET PYQs on what you've covered

### Month 4 — OBG, Paediatrics, Orthopaedics

- OBG — normal pregnancy, GDM, PIH, labour, gynaecology basics
- Paediatrics — growth, milestones, immunisation, ARI/diarrhoea
- Orthopaedics — fractures, joint diseases, bone tumours basics

### Month 5 — Remaining clinical subjects

- ENT, Ophth, Anaesthesia, Radio, Psych, Dermatology, Community Medicine

### Month 6 — Full mocks + subject triage

- **5 full-length NEET PG mocks** spaced across the month
- Identify weak subjects → re-read + re-PYQ

### Month 7 — Second revision + grand tests

- 5 more full mocks
- Solve previous 3 years of NEET PG (2022, 2023, 2024) under timed conditions

### Month 8 — Final sprint

- 10 timed mocks in the last 30 days
- **Last-week protocol:** see our [CMS + NEET PG last-week strategy](/blog/cms-and-neet-pg-last-week-shared-revision)
- Sleep ≥7 hours. Do not cram the night before.

---

## The 4-month plan (working graduate)

The 4-month plan is *intensity*. Same coverage as 8 months, but compressed.

### Month 1 — Foundation + clinical kickoff

- **Weeks 1–2:** Anatomy (high-yield) + Physiology + Biochemistry
- **Weeks 3–4:** Pathology + Pharmacology + Microbiology

### Month 2 — All clinical subjects

- **Weeks 5–6:** Medicine + Surgery
- **Weeks 7–8:** OBG + Paediatrics + remaining clinical

### Month 3 — Mocks + revision

- 8 full mocks (every 3–4 days)
- After each mock: topic-error log → re-read + re-PYQ

### Month 4 — Final sprint

- 10 timed mocks
- Subject triage in the last 2 weeks — *only* on weak areas

---

## Daily schedule variants

### 3-hour/day variant (working intern with on-duty days)

| Time | Activity |
|---|---|
| 0:00 – 1:30 | Reading |
| 1:30 – 2:30 | PYQs on the topic |
| 2:30 – 3:00 | Recall + topic-error log |

### 5-hour/day variant (typical preparation)

| Block | Activity |
|---|---|
| Block 1 (2 hr) | Reading |
| Block 2 (1.5 hr) | PYQs |
| Block 3 (1 hr) | Mock / revision |
| Block 4 (0.5 hr) | Topic-error log |

### 8-hour/day variant (full-time aspirant)

| Block | Activity |
|---|---|
| Block 1 (3 hr) | Reading |
| Block 2 (2 hr) | PYQs |
| Block 3 (1.5 hr) | Mock |
| Block 4 (1 hr) | Revision + topic-error log |
| Block 5 (0.5 hr) | Weekly full-mock review |

---

## High-yield resources

| Subject | Primary text | Companion | PYQ source |
|---|---|---|---|
| **Medicine** | Harrison | API Medicine | [CrackCMS PYQ archive](/questions?exam=NEET_PG) |
| **Surgery** | Bailey & Love (short) | Manipal Textbook | [CrackCMS PYQ archive](/questions?exam=NEET_PG) |
| **OBG** | DC Dutta | Williams Obstetrics (selective) | [CrackCMS PYQ archive](/questions?exam=NEET_PG) |
| **Paediatrics** | OP Ghai | IAP Textbook | [CrackCMS PYQ archive](/questions?exam=NEET_PG) |
| **Pathology** | Robbins (general + systemic) | Harsh Mohan | [CrackCMS PYQ archive](/questions?exam=NEET_PG) |
| **Pharmacology** | KD Tripathi | Sharma & Sharma | [CrackCMS PYQ archive](/questions?exam=NEET_PG) |
| **Microbiology** | Ananthanarayanan | Apurba Sastry | [CrackCMS PYQ archive](/questions?exam=NEET_PG) |

> See our [Best PG Medical Entrance Books](/blog/best-pg-medical-entrance-books) post for the complete shortlist with PYQ citations.

---

## Mock-test strategy on the CrackCMS Simulator

- **Diagnostic mocks:** Day 1, Day 30, Day 60 — three "no prep" mocks that establish your baseline
- **Subject tests:** 2× per week, focused on the subject you just covered
- **Grand tests:** Month 6 onward in the 8-month plan; Month 3 onward in the 4-month plan
- **Last 10 mocks:** score within ±15 marks — consistency > best score

Use the [NEET PG Simulator](/simulator) — it has the correct CBT timing, negative marking, and per-subject analysis built in.

---

## Subject triage — what to drop, what to deep-dive

### Drop (low-yield relative to time)

- Biochemistry — pure chemistry chapters (enzyme kinetics deep-dive, full metabolic pathways beyond the high-yield)
- Anatomy — microanatomy beyond the most-tested topics (nerve supply of limbs, blood supply of organs)
- Forensic Medicine — entire sections beyond the legal/medico-legal basics
- Community Medicine — PSM statistics deep-dives; focus only on national programmes

### Deep-dive (high-yield)

- Medicine — Cardiology, Endocrine, GI, Respiratory, Infectious disease
- Surgery — General surgery, ortho, anaesthesia
- OBG — pregnancy complications, labour, contraception
- Paediatrics — nephrotic syndrome, immunisation, ARI/diarrhoea
- Pharmacology — high-yield drug classes (see Month 2 plan)
- Pathology — General Pathology + Systemic Pathology (both)

---

## FAQs

### Is 4 months enough for NEET PG?

Yes, for an MBBS graduate who has been in clinical practice or active study. 4 months at 5–8 hours/day is sufficient.

### Should I solve subject tests or grand tests first?

Subject tests first. Two passes of subject tests, then two passes of grand tests.

### Is Marrow enough for NEET PG?

Marrow is enough for content but not for PYQ integration. Combine with the CrackCMS PYQ archive and Simulator.

### When should I start revision?

Month 3 of the 8-month plan; Day 60 of the 4-month plan.

### Which subject should I drop to save time?

In the 4-month plan, drop Anatomy + Physiology deep-dives. In the 8-month plan, cover everything once at lower depth on Biochemistry and Forensic Medicine.

### How many NEET PG mocks should I take?

Minimum 20 full-length mocks before the exam.

### Is coaching required for NEET PG?

No. Self-study + a strong PYQ bank + a reliable mock simulator can take you through.

---

## References

1. NBE. *NEET PG information bulletin*. [natboard.edu.in](https://natboard.edu.in/)
2. NMC. *Graduate Medical Education Regulations*. [nmc.org.in](https://www.nmc.org.in/)
3. CrackCMS. *NEET PG 2024 Cutoff (companion post)*. [cracklabs.app/blog/neet-pg-2024-cutoff-category-wise](https://cracklabs.app/blog/neet-pg-2024-cutoff-category-wise)

---

*This article is for informational purposes only. The schedule is a general recommendation; adapt to your own context.*`,
};

export default post;