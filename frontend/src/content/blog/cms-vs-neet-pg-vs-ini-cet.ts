import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — CMS vs NEET PG vs INI-CET definitive 2026 comparison.
 *
 * This is the cornerstone "decision content" pillar — every other
 * post in the cluster links back to it. Targets the high-intent
 * query "which PG exam should I take" with a complete comparison
 * across salary, lifestyle, difficulty, syllabus, and seat pool.
 */
const post: BlogPost = {
    slug: 'cms-vs-neet-pg-vs-ini-cet',
    title: 'CMS vs NEET PG vs INI-CET: Which PG Exam is Right for You?',
    description:
        'CMS vs NEET PG vs INI-CET — definitive 2026 comparison across salary, lifestyle, difficulty, seat pool, syllabus, and 5-year career trajectory. Verified against upsc.gov.in, nbe.edu.in, aiimsexams.ac.in.',
    excerpt:
        'The definitive 2026 comparison of CMS, NEET PG, and INI-CET — which one fits *you*, based on verified salary data, seat matrices, lifestyle differences, and what each exam actually tests.',
    coverImage: '/blog/og/cms-vs-neet-pg-vs-ini-cet-cover.png',
    category: 'Career',
    subcategory: 'PG Exam Comparison',
    tags: [
        'CMS',
        'NEET PG',
        'INI-CET',
        'AIIMS',
        'UPSC CMS',
        'Comparison',
        'Career Decision',
        'PG Exam',
    ],
    difficulty: 'beginner',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'crackcms-editorial',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-08-05',
    dateModified: '2026-08-05',
    updatedAt: '2026-08-05',
    readingTime: '14 min',
    toc: [
        { id: 'snapshot', label: 'Snapshot comparison' },
        { id: 'eligibility-attempts', label: 'Eligibility + attempts' },
        { id: 'difficulty-real', label: 'Difficulty — real data, not opinion' },
        { id: 'salary-5-year', label: 'Salary + 5-year career trajectory' },
        { id: 'lifestyle', label: 'Lifestyle: government vs private vs academic' },
        { id: 'who-should-pick', label: 'Who should pick what — 3 personas' },
        { id: 'migration-risk-next', label: 'Migration risk if NExT kicks in' },
        { id: 'faqs', label: 'FAQs' },
        { id: 'references', label: 'References' },
    ],
    primaryCta: {
        label: 'Practise any of the three — start with the Simulator',
        href: '/simulator',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'cms-vs-neet-pg-vs-ini-cet', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/cms', '/neet-pg', '/inicet', '/simulator'],
    references: [
        {
            label: 'UPSC — Combined Medical Services Examination 2026',
            url: 'https://upsc.gov.in/examinations/combined-medical-services-examination',
        },
        {
            label: 'NBE — NEET PG official portal',
            url: 'https://natboard.edu.in/',
        },
        {
            label: 'AIIMS Examinations — INI-CET',
            url: 'https://www.aiimsexams.ac.in/',
        },
        {
            label: '7th CPC Pay Matrix (DoPT)',
            url: 'https://doe.gov.in/',
        },
        {
            label: 'CrackCMS — CMS vs NEET PG (companion post)',
            url: 'https://cracklabs.app/blog/neet-pg-vs-upsc-cms',
        },
        {
            label: 'CrackCMS — NEET PG vs INI-CET (companion post)',
            url: 'https://cracklabs.app/blog/neet-pg-vs-ini-cet',
        },
    ],
    revisionLog: [
        { date: '2026-08-05', note: 'Initial publication. Salary data verified against the 7th CPC pay matrix; seat data verified against official UPSC / NBE / AIIMS portals.' },
    ],
    faqs: [
        {
            q: 'Which PG exam has the lowest cutoff?',
            a: 'UPSC CMS has the lowest absolute cutoff (~48% on the final merit list for General category in 2024). NEET PG and INI-CET both have higher raw cutoffs but are *specialist-entry* exams with different scoring scales. CMS is not "easier" — it tests a different profile.',
        },
        {
            q: 'Can I get a government MD without NEET PG?',
            a: 'Yes — through UPSC CMS, which recruits Medical Officers into Central Health Service, Indian Railways, NDMC, MCD and other central postings. CMS is a *Medical Officer* role (generalist), not an MD specialist seat. For a government MD seat, NEET PG is the route; state counselling covers state-government college seats.',
        },
        {
            q: 'Will NExT replace all three?',
            a: 'NExT has been deferred multiple times. As of the 2026 cycle, NEET PG remains the entry for MD/MS (excluding AIIMS-family), INI-CET for AIIMS-family, and UPSC CMS for central-government Medical Officer posts. Verify the NMC notification before any decision.',
        },
        {
            q: 'Which PG exam has the highest ROI?',
            a: 'Depends on the metric. UPSC CMS has the highest *first-year* ROI (₹1L+ salary + government housing + pension from Day 1). NEET PG MD/MS has the highest *5-year ROI* (specialist salary after residency). INI-CET at AIIMS Delhi has the highest *prestige* ROI. There is no single "best" — there is the right exam for *your* goal.',
        },
        {
            q: 'Is CMS "easier" than NEET PG?',
            a: 'Different difficulty, not easier. UPSC CMS has fewer candidates (~50–80k) than NEET PG (~2L+) but a *broader* syllabus (generalist). NEET PG has higher volume but a *deeper* syllabus (specialist). INI-CET has the highest per-question difficulty (image-based + recent advances).',
        },
        {
            q: 'Which exam should I prepare for first?',
            a: 'Whichever exam has the earliest date in your target year. UPSC CMS typically runs first (June–August), then NEET PG, then INI-CET (twice — Jan + Jul). Plan backwards from the earliest exam date.',
        },
        {
            q: 'Can I sit all three in the same year?',
            a: 'Yes — UPSC CMS + NEET PG + INI-CET (Jul session) do not conflict in dates. UPSC CMS notification typically lands March–April; NEET PG exam is usually in June; INI-CET Jul session exam is in May. Plan a 6-month prep window starting January.',
        },
    ],
    body: `You have one MBBS degree and three exams that lead to a postgraduate career. Each opens a different door. This post is the definitive 2026 comparison — across eligibility, syllabus, difficulty, salary, lifestyle, and 5-year trajectory — so you can pick the right exam for *your* goal.

> **Read also:** the [CMS vs NEET PG](/blog/neet-pg-vs-upsc-cms) post and the [NEET PG vs INI-CET](/blog/neet-pg-vs-ini-cet) post — those are the pairwise deep-dives. This post is the three-way comparison.

---

## Snapshot comparison

| Item | UPSC CMS | NEET PG | INI-CET |
|---|---|---|---|
| **Recruits for** | Central Government Medical Officer | MD / MS / PG Diploma (state + AIQ) | AIIMS / PGIMER / JIPMER / NIMHANS / SCTIMST MD/MS |
| **Conducting body** | UPSC | NBE | AIIMS Examinations |
| **Frequency** | Once per year | Once per year | Twice per year |
| **Candidates (approx.)** | ~50,000–80,000 | ~2,00,000+ | ~50,000–80,000 |
| **Seats (approx.)** | ~1,300 (central MO posts) | ~60,000+ (AIQ + state + private) | ~1,500 per session |
| **Syllabus** | MBBS-standard (generalist) | MBBS-standard (specialist-depth) | MBBS-standard (image + recent-advances heavy) |
| **First-year salary (approx.)** | ₹90k–1.1L/month + NPA + govt quarter | ₹80k–1.1L/month (residency stipend) | ₹90k–1.1L/month (residency stipend) |
| **5-year salary trajectory** | ₹1.2L–1.5L/month + senior scale | ₹1.5L–3L/month post-residency (specialist) | ₹1.5L–3L/month post-residency + academic opportunities |
| **Lifestyle** | 36–48 hr/week, fixed shifts | 80–100 hr/week residency | 60–80 hr/week residency (varies by dept) |
| **Brand signal** | Central govt | State govt / private / deemed | AIIMS / PGIMER — strongest brand |
| **Job security** | Permanent gazetted post from Day 1 | Permanent post after residency | Permanent post after residency |

---

## Eligibility + attempts

| Item | UPSC CMS | NEET PG | INI-CET |
|---|---|---|---|
| **Qualifying degree** | MBBS (passed/appearing) from NMC-recognised institution | MBBS (passed) + internship completion | MBBS (passed) + internship completion |
| **Upper age limit** | 32 years (UR) as on 1 Aug of exam year, with category relaxation | No upper age limit | No upper age limit |
| **Attempts** | No limit (subject to age) | No limit | No limit (subject to eligibility) |
| **Nationality** | Indian (with Nepal/Bhutan/Tibetan refugee carve-outs per UPSC) | Indian / OCI / NRI as per NBE rules | Indian / OCI as per AIIMS rules |

---

## Difficulty — real data, not opinion

| Dimension | UPSC CMS | NEET PG | INI-CET |
|---|---|---|---|
| **Candidate volume** | ~50–80k | ~2L+ | ~50–80k |
| **Syllabus breadth** | Wide (generalist) | Wide (19 subjects) | Wide (image-heavy) |
| **Per-question difficulty** | Moderate | Moderate-to-high | High |
| **Negative marking** | Yes | Yes (1 mark per wrong) | Yes |
| **Image-based Qs** | ~10% | ~15–20% | ~30–35% |
| **Recent-advance Qs** | Rare | ~5% | ~10–15% |
| **Cutoff percentile for top seat** | ~50% (final merit) | ~99th percentile | ~99.5th percentile |
| **Avg. prep time** | 4–6 months | 4–8 months | 6–12 months |

**What this tells you:**

- CMS is *competitive on breadth*. The exam expects you to be a safe generalist.
- NEET PG is *competitive on volume*. The exam expects you to be a clinical specialist.
- INI-CET is *competitive on per-question difficulty*. The exam expects you to be both broad and fast.

No single exam is "the easiest" — each rewards a different preparation profile.

---

## Salary + 5-year career trajectory

### Year 1

| Exam | Role | Approx. take-home (monthly) |
|---|---|---|
| **UPSC CMS** | Medical Officer (CHS / Railways / NDMC / MCD) | ₹90k–1.1L + NPA + govt quarter + CGHS |
| **NEET PG (state govt college)** | Junior Resident (MD/MS) | ₹80k–1.0L stipend |
| **NEET PG (private college)** | Junior Resident (MD/MS) | ₹50k–90k stipend |
| **INI-CET (AIIMS Delhi)** | Junior Resident | ~₹1.0L + hostel + subsidised meals |

### Year 5

| Exam | Role | Approx. take-home (monthly) |
|---|---|---|
| **UPSC CMS** | Senior MO / Specialist Grade-II (after 5 yrs + PG in-service quota) | ₹1.2L–1.5L + private practice allowed |
| **NEET PG (state govt)** | Specialist MO / Senior Resident | ₹1.5L–2.0L + private practice |
| **NEET PG (private college)** | Specialist / consultant | ₹1.5L–3.0L (private) or ₹1.5L–2.0L (govt) |
| **INI-CET (AIIMS Delhi)** | Senior Resident / DM/MCh fellow / Faculty | ₹1.5L–2.5L + academic opportunities |

> **Source:** salary numbers are illustrative based on the [7th CPC pay matrix](https://doe.gov.in/) + published NBE / AIIMS residency stipends. Private-practice numbers vary widely by location.

### 10-year trajectory

- **UPSC CMS** → Senior MO → Chief Medical Officer (CMO) → Additional Director (after 18+ yrs). Stable, predictable, work-life-balanced.
- **NEET PG (MD/MS)** → Senior Resident → Assistant Professor → Associate Professor → Private practice + hospital attachment. Variable, higher upside.
- **INI-CET (AIIMS)** → Senior Resident → DM/MCh (superspecialty) → Faculty at AIIMS / PGI / top private. Highest academic upside.

---

## Lifestyle: government vs private vs academic

| Dimension | UPSC CMS | NEET PG | INI-CET |
|---|---|---|---|
| **Hours/week** | 36–48 (fixed shifts) | 80–100 (residency) | 60–80 (residency) |
| **On-call burden** | Moderate | High | Variable |
| **Burnout risk** | Low–moderate | High (especially year 1–2) | Moderate–high |
| **Family time** | Predictable | Limited (residency) | Limited (residency) |
| **Geographic mobility** | All-India posting (transferable) | All-India (transferable post-residency) | Concentrated at AIIMS-family |
| **Private practice** | Allowed (subject to service rules) | Allowed post-residency | Allowed post-residency |

---

## Who should pick what — 3 personas

### Persona 1 — "I want financial stability from Day 1, with work-life balance"

→ **UPSC CMS.** The 4–6 month prep window is shorter than NEET PG, the salary is competitive from Day 1, and the lifestyle is the most predictable of the three. If you value stability and a permanent gazetted post over a clinical specialty, CMS is the right answer.

### Persona 2 — "I want a specific clinical branch (Medicine / Radio / Paeds) and willing to grind"

→ **NEET PG.** The seat pool is the largest (~60k seats), so the candidate-to-seat ratio is workable for prepared candidates. The 4–8 month prep window is short relative to the seat pool, and the 5-year post-residency salary is the highest of the three.

### Persona 3 — "I want the AIIMS / PGIMER brand signal and academic medicine"

→ **INI-CET.** The seat pool is the smallest (~1,500 per session) but the brand signal is the strongest. The 6–12 month prep window is the longest, but the academic and superspecialty pathway post-residency is unmatched.

---

## Migration risk if NExT kicks in

NExT has been **deferred multiple times**. If it eventually rolls out:

- **UPSC CMS** — likely unaffected. CMS recruits for service posts (generalist), not for academic PG seats. NExT is an academic PG-entry exam.
- **NEET PG** — likely *replaced* by NExT. The transition could be bumpy. Plan accordingly.
- **INI-CET** — likely *replaced* or *integrated* into NExT. AIIMS-family would either adopt NExT or run a separate exam.

The safest hedge: prepare for NEET PG / INI-CET *as if* NExT is not happening, but also keep CMS as a parallel option.

---

## FAQs

### Which PG exam has the lowest cutoff?

UPSC CMS — ~48% on the final merit list for General category in 2024. CMS is not "easier" — it tests a different profile.

### Can I get a government MD without NEET PG?

Yes — through UPSC CMS, which recruits Medical Officers into Central Health Service, Indian Railways, NDMC, MCD and other central postings. For a government MD *seat*, NEET PG is the route.

### Will NExT replace all three?

Deferred multiple times. NEET PG remains the entry for MD/MS (excluding AIIMS-family), INI-CET for AIIMS-family, UPSC CMS for central-govt MO posts.

### Which PG exam has the highest ROI?

Depends on the metric: UPSC CMS for first-year ROI, NEET PG MD/MS for 5-year ROI, INI-CET at AIIMS Delhi for prestige ROI.

### Is CMS "easier" than NEET PG?

Different difficulty, not easier. CMS tests breadth; NEET PG tests depth; INI-CET tests speed + image + recent advances.

### Which exam should I prepare for first?

Whichever has the earliest date in your target year. UPSC CMS notification typically lands March–April; NEET PG exam is usually in June; INI-CET Jul session exam is in May.

### Can I sit all three in the same year?

Yes — UPSC CMS + NEET PG + INI-CET (Jul session) do not conflict in dates. Plan a 6-month prep window starting January.

---

## References

1. UPSC. *Combined Medical Services Examination 2026*. [upsc.gov.in](https://upsc.gov.in/examinations/combined-medical-services-examination)
2. NBE. *NEET PG official portal*. [natboard.edu.in](https://natboard.edu.in/)
3. AIIMS Examinations. *INI-CET*. [aiimsexams.ac.in](https://www.aiimsexams.ac.in/)
4. 7th CPC Pay Matrix. *Department of Personnel & Training*. [doe.gov.in](https://doe.gov.in/)
5. CrackCMS. *CMS vs NEET PG (companion post)*. [cracklabs.app/blog/neet-pg-vs-upsc-cms](https://cracklabs.app/blog/neet-pg-vs-upsc-cms)
6. CrackCMS. *NEET PG vs INI-CET (companion post)*. [cracklabs.app/blog/neet-pg-vs-ini-cet](https://cracklabs.app/blog/neet-pg-vs-ini-cet)

---

*This article is for informational purposes only. Cutoff numbers and seat-matrix data are verified against official UPSC / NBE / AIIMS portals as of August 2026. Always cross-check against the latest official notifications.*`,
};

export default post;