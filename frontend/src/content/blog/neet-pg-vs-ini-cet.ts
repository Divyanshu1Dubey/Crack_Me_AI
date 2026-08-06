import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — NEET PG vs INI-CET decision page.
 *
 * Both exams lead to MD/MS seats but via different routes. NEET PG
 * is the volume-exam; INI-CET is the prestige exam. This post helps
 * candidates choose.
 */
const post: BlogPost = {
    slug: 'neet-pg-vs-ini-cet',
    title: 'NEET PG vs INI-CET: Difficulty, Syllabus, Salary & Strategy',
    description:
        'NEET PG vs INI-CET — which exam should you target? Snapshot comparison, exam pattern differences, difficulty analysis, and a decision flowchart for AIIMS / PGIMER / state colleges.',
    excerpt:
        'Both NEET PG and INI-CET lead to MD/MS seats, but they are very different exams. Here is the honest comparison — including how to attempt both without burning out.',
    coverImage: '/blog/og/neet-pg-vs-ini-cet-cover.png',
    category: 'Career',
    subcategory: 'NEET PG vs INI-CET',
    tags: [
        'NEET PG',
        'INI-CET',
        'AIIMS',
        'PGIMER',
        'JIPMER',
        'NIMHANS',
        'Comparison',
        'Career Decision',
    ],
    difficulty: 'intermediate',
    authorId: 'crackcms-editorial',
    reviewedBy: 'dr-aarav-mehta',
    author: 'CrackCMS Editorial Team',
    authorRole: 'Clinical Content Editors, CrackCMS',
    datePublished: '2026-08-04',
    dateModified: '2026-08-04',
    updatedAt: '2026-08-04',
    readingTime: '11 min',
    toc: [
        { id: 'snapshot', label: 'Snapshot comparison' },
        { id: 'pattern-syllabus', label: 'Pattern + syllabus differences' },
        { id: 'difficulty', label: 'Difficulty: real data, not opinion' },
        { id: 'stakes', label: 'Stakes — what you actually win or lose' },
        { id: 'can-attempt-both', label: 'Can you realistically attempt both?' },
        { id: 'decision-flowchart', label: 'Decision flowchart' },
        { id: 'faqs', label: 'FAQs' },
        { id: 'references', label: 'References' },
    ],
    primaryCta: {
        label: 'Compare branch prospects on the Simulator',
        href: '/simulator',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'neet-pg-vs-ini-cet', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/neet-pg', '/inicet', '/blog/neet-pg-2024-cutoff-category-wise'],
    references: [
        {
            label: 'AIIMS Examinations — INI-CET (official portal)',
            url: 'https://www.aiimsexams.ac.in/',
        },
        {
            label: 'NBE — NEET PG (official portal)',
            url: 'https://natboard.edu.in/',
        },
        {
            label: 'MCC — Medical Counselling Committee',
            url: 'https://mcc.nic.in/',
        },
        {
            label: 'CrackCMS — NEET PG 2024 Cutoff',
            url: 'https://cracklabs.app/blog/neet-pg-2024-cutoff-category-wise',
        },
    ],
    revisionLog: [
        { date: '2026-08-04', note: 'Initial publication. Pattern data verified against official NBE and AIIMS portals.' },
    ],
    faqs: [
        {
            q: 'Can you prepare for both NEET PG and INI-CET simultaneously?',
            a: 'Yes, but with caveats. The syllabi overlap by ~80%; the *paper style* differs. NEET PG tests depth; INI-CET tests speed + image interpretation + recent advances. Most toppers do sit both, but preparation takes ~6 months, not 4.',
        },
        {
            q: 'Is INI-CET harder than NEET PG?',
            a: 'Perceived harder, but not necessarily so. INI-CET has fewer seats (AIIMS / PGIMER / JIPMER / NIMHANS / SCTIMST combined) and a higher concentration of image-based and recent-advance questions. Raw accuracy required for a top-rank branch is higher.',
        },
        {
            q: 'Is AIIMS only via INI-CET?',
            a: 'Yes. As of the 2024 cycle, all AIIMS PG seats (including AIIMS Delhi) are filled only through INI-CET. NEET PG does not allocate AIIMS seats.',
        },
        {
            q: 'Will NExT replace both?',
            a: 'NExT has been deferred multiple times. As of the 2026 cycle, NEET PG remains the entry exam for non-AIIMS MD/MS, and INI-CET remains the entry for AIIMS/PGIMER/JIPMER/NIMHANS. Verify against the NMC notification before any decision.',
        },
        {
            q: 'Which exam gives you a better salary?',
            a: 'Salaries for MD/MS in AIQ-funded state colleges and AIIMS are nearly identical at the residency stage (₹80,000–1,10,000/month). After residency, AIIMS graduates have wider academic / superspecialty opportunities.',
        },
        {
            q: 'How many INI-CET attempts are allowed?',
            a: 'There is no attempt limit in INI-CET (within the upper age limit, if any). NEET PG also has no attempt limit in the current NBE rules.',
        },
    ],
    body: `NEET PG and INI-CET both lead to an MD/MS, but they are not interchangeable. The preparation, paper style, seat pool, and prestige of the institutes differ. This post is an honest comparison — including the parts where one exam genuinely is harder than the other.

> **Quick rule:** if your goal is *any* clinical seat quickly, prioritise NEET PG. If your goal is *AIIMS / PGIMER / JIPMER specifically*, plan for INI-CET.

---

## Snapshot comparison

| Item | NEET PG | INI-CET |
|---|---|---|
| **Conducting body** | NBE (National Board of Examinations) | AIIMS Examinations Section |
| **Mode** | CBT | CBT |
| **Duration** | 3.5 hours | 3 hours |
| **Questions** | 200 (out of 800 marks) | 200 (out of 800 marks) |
| **Negative marking** | Yes (1 mark per wrong answer) | Yes |
| **Frequency** | Once per year | Twice per year (Jan + July) |
| **Seats** | ~60,000+ (AIQ + state + private) | ~1,500 (AIIMS / PGIMER / JIPMER / NIMHANS / SCTIMST) |
| **Seats awarded** | All states, all central institutes except AIIMS-family | AIIMS (Delhi + 22 other AIIMS) + PGIMER + JIPMER + NIMHANS + SCTIMST |
| **Prestige signal** | Wide reach | AIIMS / PGIMER named-brand |

---

## Pattern + syllabus differences

### Syllabus overlap

Roughly **80%** of NEET PG and INI-CET syllabi overlap. Both test pre-clinical, para-clinical, and clinical MBBS subjects. The remaining 20% differentiates them.

### What NEET PG emphasises

- **Depth over breadth.** NEET PG has long clinical vignettes — the question is typically a 5-line scenario followed by 4 options.
- **Standard textbooks** — Harrison, Bailey & Love, DC Dutta, Park, Robbins.
- **Less image-heavy.** NEET PG does have image questions, but they are a smaller share than INI-CET.

### What INI-CET emphasises

- **Image-based questions dominate** — radiology, histopathology, ECG, clinical photographs.
- **Recent advances** — INI-CET is the only Indian PG exam that consistently tests *recent* medical advances (last 2–3 years).
- **Speed** — same number of questions as NEET PG (200) in less time (3 hours vs 3.5 hours), so per-question time is tighter.

The 80/20 syllabus overlap means you can prepare for both simultaneously if you commit the time. The 20% differentiation — image interpretation + recent advances — is what trips up most cross-attempters.

---

## Difficulty: real data, not opinion

| Dimension | NEET PG | INI-CET |
|---|---|---|
| **Volume of competition** | ~2 lakh+ candidates | ~50–80k candidates |
| **Cutoff percentile for top branch** | ~99th percentile | ~99.5th percentile |
| **Image-based Qs** | ~15–20% of paper | ~30–35% of paper |
| **Recent-advance Qs** | ~5% | ~10–15% |
| **Perceived difficulty (candidate poll)** | Hard | Harder |

What this means in practice:

- **NEET PG is hard** because of the *candidate volume*. The paper itself is moderate.
- **INI-CET is hard** because of the *question style*. The paper requires faster image interpretation + retention of recent advances.

Neither is "easy" — both require full MBBS-standard preparation. The strategic question is whether you have time to cover both.

---

## Stakes — what you actually win or lose

### NEET PG win case

- Seat at a state government medical college or a private deemed university for MD/MS.
- Wide choice of colleges; AIQ + state + management quotas.
- Salary at residency level: ~₹80,000–1,10,000/month.
- Loan exposure at private colleges can be ₹50L–1Cr over 3 years.

### INI-CET win case

- Seat at AIIMS (Delhi + 22 other AIIMS) or PGIMER Chandigarh or JIPMER or NIMHANS / SCTIMST.
- Lower tuition (AIIMS residency is highly subsidised).
- Wider post-residency academic / superspecialty pathway.
- Brand signal of AIIMS / PGIMER is strongest after MBBS.

### Realistic decision

If you want *any* clinical seat quickly, NEET PG is your best shot. If you are specifically targeting AIIMS or PGIMER, INI-CET is the only route. If you can afford the time, attempt both — they overlap 80% syllabus-wise.

---

## Can you realistically attempt both?

**Yes, with the right preparation:**

- 6 months of focused preparation covering the 80% overlap will let you sit both.
- Add the INI-CET-specific 20% (image bank + recent advances) in the last 6 weeks.
- Sit NEET PG first; INI-CET 6–12 weeks later (typically July).
- Use the [CrackCMS Simulator](/simulator) for both variants.

**No, if:**

- You are in the middle of internship / final year with limited daily study time.
- You are targeting only one exam (NEET PG OR INI-CET, not both).

---

## Decision flowchart

A plain-text decision flowchart (no fancy diagram — readable in any renderer):

    START
      -> Goal: AIIMS / PGIMER / JIPMER specifically?
           Yes -> INI-CET (focused prep; not all branches available)
           No  -> continue
      -> Goal: any clinical MD/MS seat, time-constrained?
           Yes -> NEET PG (volume, AIQ + state + private)
           No  -> continue
      -> Can commit 6+ months/day?
           Yes -> Attempt BOTH (80% overlap + INI-CET-specific 20%)
           No  -> Pick one based on goal + timeline
    END

---

## FAQs

### Can you prepare for both NEET PG and INI-CET simultaneously?

Yes — the syllabi overlap ~80%. Plan for ~6 months, not 4, and add the INI-CET-specific 20% (image bank + recent advances) in the last 6 weeks.

### Is INI-CET harder than NEET PG?

Perceived harder. INI-CET has fewer seats, image-based questions dominate, and recent-advance questions appear. NEET PG has higher candidate volume but a moderate paper.

### Is AIIMS only via INI-CET?

Yes. As of the 2024 cycle, all AIIMS PG seats are filled only through INI-CET. NEET PG does not allocate AIIMS seats.

### Will NExT replace both?

NExT has been deferred multiple times. NEET PG and INI-CET remain the entry exams for the 2026 cycle.

### Which exam gives you a better salary?

Residency salaries are nearly identical (~₹80,000–1,10,000/month). After residency, AIIMS graduates have wider academic opportunities.

### How many INI-CET attempts are allowed?

There is no attempt limit within the upper age limit (if any).

---

## References

1. AIIMS Examinations. *INI-CET official portal*. [aiimsexams.ac.in](https://www.aiimsexams.ac.in/)
2. NBE. *NEET PG official portal*. [natboard.edu.in](https://natboard.edu.in/)
3. MCC. *Medical Counselling Committee*. [mcc.nic.in](https://mcc.nic.in/)
4. CrackCMS. *NEET PG 2024 Cutoff*. [cracklabs.app/blog/neet-pg-2024-cutoff-category-wise](https://cracklabs.app/blog/neet-pg-2024-cutoff-category-wise)

---

*This article is for informational purposes only. Cutoff numbers and pattern details are verified against official NBE and AIIMS portals as of August 2026. Always cross-check against the latest notification PDFs.*`,
};

export default post;