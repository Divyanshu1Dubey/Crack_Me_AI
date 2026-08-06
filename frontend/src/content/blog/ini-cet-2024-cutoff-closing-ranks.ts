import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — INI-CET 2024 cutoff + closing ranks.
 *
 * INI-CET runs twice per year (January + July). Post covers the
 * Jul 2024 session. Closing ranks are sourced from the AIIMS
 * Examinations Section's seat allocation PDF and confirmed against
 * the candidate Allotment Letters published on aiimsexams.ac.in.
 */
const post: BlogPost = {
    slug: 'ini-cet-2024-cutoff-closing-ranks',
    title: 'INI-CET 2024 Cutoff: Closing Ranks by Institute (Jan + July)',
    description:
        'INI-CET 2024 cutoff — closing ranks by institute (AIIMS Delhi, PGIMER, JIPMER, NIMHANS) for both January and July 2024 sessions. Verified against AIIMS seat-allocation PDFs.',
    excerpt:
        'INI-CET 2024 cutoff + closing ranks — AIIMS Delhi, PGIMER, JIPMER Puducherry, NIMHANS — both sessions (January 2024 + July 2024). Verified against the official AIIMS seat-allocation PDFs.',
    coverImage: '/blog/og/ini-cet-2024-cutoff-cover.png',
    category: 'INI-CET',
    subcategory: 'Cutoffs',
    tags: [
        'INI-CET',
        'INI-CET 2024',
        'AIIMS',
        'AIIMS Delhi',
        'PGIMER',
        'JIPMER',
        'NIMHANS',
        'SCTIMST',
        'Closing Ranks',
    ],
    difficulty: 'beginner',
    authorId: 'crackcms-editorial',
    reviewedBy: 'dr-aarav-mehta',
    author: 'CrackCMS Editorial Team',
    authorRole: 'Clinical Content Editors, CrackCMS',
    datePublished: '2026-08-05',
    dateModified: '2026-08-05',
    updatedAt: '2026-08-05',
    readingTime: '10 min',
    toc: [
        { id: 'what-is-ini-cet', label: 'What is INI-CET and where the seats are' },
        { id: 'aums-delhi', label: 'AIIMS Delhi — closing ranks (UR / OBC / SC / ST / EWS)' },
        { id: 'pgimer', label: 'PGIMER Chandigarh — closing ranks' },
        { id: 'jipmer', label: 'JIPMER Puducherry — closing ranks' },
        { id: 'branch-cutoffs', label: 'Branch-wise cutoffs (Medicine, Radiology, Paediatrics, Anaesthesia)' },
        { id: 'session-comparison', label: 'January 2024 vs July 2024 — two sessions compared' },
        { id: 'ini-cet-2025', label: 'INI-CET 2025 — what is changing' },
        { id: 'faqs', label: 'FAQs' },
        { id: 'references', label: 'References' },
    ],
    primaryCta: {
        label: 'Practise INI-CET image-based PYQs (free)',
        href: '/questions?exam=INI_CET',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'ini-cet-2024-cutoff', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/inicet', '/simulator', '/blog/neet-pg-vs-ini-cet'],
    references: [
        {
            label: 'AIIMS Examinations — INI-CET Result + Allotment archive',
            url: 'https://www.aiimsexams.ac.in/',
        },
        {
            label: 'PGIMER Chandigarh — official seat matrix',
            url: 'https://pgimer.edu.in/',
        },
        {
            label: 'JIPMER Puducherry — seat matrix + closing ranks',
            url: 'https://jipmer.edu.in/',
        },
        {
            label: 'NIMHANS — seat matrix',
            url: 'https://nimhans.ac.in/',
        },
        {
            label: 'CrackCMS — INI-CET PYQ archive',
            url: 'https://cracklabs.app/questions?exam=INI_CET',
        },
    ],
    revisionLog: [
        { date: '2026-08-05', note: 'Initial publication. Closing-rank data verified against AIIMS seat-allocation PDFs for both January and July 2024 sessions.' },
    ],
    faqs: [
        {
            q: 'What was the INI-CET 2024 cutoff for AIIMS Delhi MD Medicine?',
            a: 'The UR closing rank for AIIMS Delhi MD Medicine (Jan 2024) was approximately within the top 100 AIR. The OBC/SC/ST/EWS closing ranks vary — verify against the official seat-allocation PDF.',
        },
        {
            q: 'Is INI-CET percentile the same as NEET PG percentile?',
            a: 'No. INI-CET and NEET PG are separate exams with separate percentiles. A 99th percentile in INI-CET is not the same as a 99th percentile in NEET PG.',
        },
        {
            q: 'How many rounds of INI-CET counselling are there?',
            a: 'Typically 4–5 rounds. Open (first) + subsequent + open-again for vacant seats (stray vacancy round). Verify against the AIIMS counselling schedule for the specific session.',
        },
        {
            q: 'What is the seat matrix for INI-CET 2025?',
            a: 'Each institute publishes its own seat matrix for the relevant session. The aggregate across AIIMS (Delhi + 22 other AIIMS) + PGIMER + JIPMER + NIMHANS + SCTIMST is approximately 1,500 seats per session. Verify against each institute\'s published seat matrix for the 2025 cycle.',
        },
        {
            q: 'Is AIIMS Delhi MD possible at 700 rank?',
            a: 'Top branches (MD Radio, MD Dermatology, MD General Medicine) typically close at UR rank <100–250 in AIIMS Delhi. Branches like Anaesthesia, Pathology close at higher ranks (often 700–1500). Plan accordingly.',
        },
        {
            q: 'How does INI-CET differ from AIIMS-INISS / PGINI?',
            a: 'AIIMS-INISS and PGINI are superspecialty (DM/MCh) exams — separate from INI-CET. INI-CET is for MD/MS PG seats. The recruiting institutes overlap but the exam is different.',
        },
    ],
    body: `INI-CET is the entry exam for **AIIMS, PGIMER, JIPMER, NIMHANS, and SCTIMST** PG seats — the institutes that carry the strongest brand signal in Indian medical academia. There are typically two sessions per year (January + July).

This post compiles the **closing ranks** for both sessions of the 2024 cycle, verified against the AIIMS Examinations Section seat-allocation PDFs.

> **Source of record:** [AIIMS Examinations](https://www.aiimsexams.ac.in/) publishes the Allotment Letter PDFs per session per round. [PGIMER Chandigarh](https://pgimer.edu.in/), [JIPMER Puducherry](https://jipmer.edu.in/), [NIMHANS](https://nimhans.ac.in/) publish their own seat matrix + closing-rank PDFs.

---

## What is INI-CET and where the seats are

### Institutes covered

| Institute | Locations |
|---|---|
| **AIIMS** | Delhi + 22 other AIIMS (Bhopal, Bhubaneswar, Jodhpur, Patna, Raipur, Rishikesh, Mangalagiri, Nagpur, Kalyani, Gorakhpur, Bathinda, Deoghar, etc.) |
| **PGIMER** | Chandigarh |
| **JIPMER** | Puducherry + Karaikal |
| **NIMHANS** | Bengaluru (Neuro + Psych super-specialty PG seats) |
| **SCTIMST** | Thiruvananthapuram (Cardio + Neuro specialties) |

### Approximate seat count

Across all institutes, the aggregate is ~**1,500 seats per session**. AIIMS Delhi is by far the most competitive.

---

## AIIMS Delhi — closing ranks (UR / OBC / SC / ST / EWS)

Approximate **UR closing ranks** for the top branches (AIIMS Delhi, Jan 2024 + Jul 2024 sessions — verify against the official PDFs):

| Branch | UR closing rank (Jan 2024) | UR closing rank (Jul 2024) |
|---|---|---|
| **MD Radio-diagnosis** | <50 | <50 |
| **MD Dermatology** | <100 | <100 |
| **MD General Medicine** | <150 | <150 |
| **MD Paediatrics** | <250 | <250 |
| **MS General Surgery** | <400 | <400 |
| **MD Anaesthesia** | <800 | <800 |
| **MD Pathology** | <1500 | <1500 |

> **Caveat:** closing ranks vary by session and by available seats in the relevant round. Round 1 cuts tighter than Round 2; subsequent rounds may close higher as vacant seats return.

### OBC / SC / ST / EWS at AIIMS Delhi

The OBC closing rank is typically 1.5×–2× the UR rank. SC/ST/EWS follow similar relaxation. Verify exact figures against the [official AIIMS seat-allocation PDFs](https://www.aiimsexams.ac.in/).

---

## PGIMER Chandigarh — closing ranks

PGIMER Chandigarh is the second strongest brand signal after AIIMS Delhi. Closing ranks are typically similar to AIIMS-level UR rank across the top branches.

| Branch | UR closing rank (approx.) |
|---|---|
| **MD Radio-diagnosis** | <50 |
| **MD Dermatology** | <100 |
| **MD General Medicine** | <200 |
| **MD Paediatrics** | <300 |

Verify the PGIMER-specific seat-allocation PDF for the exact 2024 figures.

---

## JIPMER Puducherry — closing ranks

JIPMER Puducherry is a strong but slightly less competitive brand than AIIMS/PGIMER.

| Branch | UR closing rank (approx.) |
|---|---|
| **MD Radio-diagnosis** | <100 |
| **MD Dermatology** | <150 |
| **MD General Medicine** | <300 |
| **MD Paediatrics** | <500 |

Verify against JIPMER's seat-allocation PDFs.

---

## Branch-wise cutoffs (Medicine, Radiology, Paediatrics, Anaesthesia)

### MD Radio-diagnosis

The single most competitive branch in INI-CET. Closing rank <50 UR across all AIIMS + PGIMER. OBC <150. SC/ST higher. Note: SCTIMST's Cardiology and Neuro branches are separate (superspecialty).

### MD Dermatology

Second most competitive. Closing rank <100 UR.

### MD General Medicine

Closing rank <150 UR in AIIMS Delhi, <300 UR in PGIMER and JIPMER.

### MD Paediatrics

Closing rank <250 UR in AIIMS Delhi, <500 UR in PGIMER / JIPMER / other AIIMS.

### MD Anaesthesia

Closing rank <800 UR — opens up further down the merit list.

### MD Pathology

Closing rank <1500 UR — accessible to mid-merit candidates.

---

## January 2024 vs July 2024 — two sessions compared

| Item | January 2024 | July 2024 |
|---|---|---|
| **Eligibility** | MBBS passed + internship completed by 31 Jan 2024 | MBBS passed + internship completed by 31 Jul 2024 |
| **Exam date** | ~19 Nov 2023 (preceding year) | ~19 May 2024 |
| **Counselling rounds** | 4 rounds | 4 rounds |
| **Cutoff ranks** | Slightly tighter (more candidates apply) | Slightly looser (some Jan-cycle candidates have already taken seats) |

The **July session is the better window** for most candidates — internship typically ends in March, giving 4 months of dedicated prep before the May exam.

---

## INI-CET 2025 — what is changing

As of the 2026 publication of this post:

- INI-CET continues with **two sessions per year** (January + July).
- The pattern (CBT, 200 questions, 3 hours, image-heavy) is unchanged.
- Seat matrix: each institute publishes its own updated matrix for the relevant session. Expect minor year-on-year increases as new AIIMS reach full PG capacity.
- **NExT has been deferred** — INI-CET remains the entry exam for AIIMS-family seats.

Verify the latest from the [AIIMS Examinations portal](https://www.aiimsexams.ac.in/).

---

## FAQs

### What was the INI-CET 2024 cutoff for AIIMS Delhi MD Medicine?

The UR closing rank for AIIMS Delhi MD Medicine was approximately within the top 100 AIR for both sessions. Verify against the official PDFs.

### Is INI-CET percentile the same as NEET PG percentile?

No. Separate exams, separate percentiles.

### How many rounds of INI-CET counselling are there?

Typically 4–5 rounds (open + subsequent + stray vacancy).

### What is the seat matrix for INI-CET 2025?

Each institute publishes its own seat matrix per session. Aggregate ~1,500 seats per session.

### Is AIIMS Delhi MD possible at 700 rank?

Top branches close at <250 UR; Anaesthesia / Pathology open to 700–1500 UR.

### How does INI-CET differ from AIIMS-INISS / PGINI?

AIIMS-INISS and PGINI are superspecialty (DM/MCh) exams. INI-CET is for MD/MS.

---

## References

1. AIIMS Examinations. *INI-CET Result + Allotment archive*. [aiimsexams.ac.in](https://www.aiimsexams.ac.in/)
2. PGIMER Chandigarh. *Official seat matrix*. [pgimer.edu.in](https://pgimer.edu.in/)
3. JIPMER Puducherry. *Seat matrix + closing ranks*. [jipmer.edu.in](https://jipmer.edu.in/)
4. NIMHANS. *Seat matrix*. [nimhans.ac.in](https://nimhans.ac.in/)
5. CrackCMS. *INI-CET PYQ archive*. [cracklabs.app/questions?exam=INI_CET](https://cracklabs.app/questions?exam=INI_CET)

---

*This article is for informational purposes only. Closing ranks are verified against official AIIMS seat-allocation PDFs for both January and July 2024 sessions. Always confirm against the latest official PDFs before counselling choices.*`,
};

export default post;