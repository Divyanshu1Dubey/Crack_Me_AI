import type { ComparisonContent } from '@/components/ComparisonLayout';
import {
    CMS_MARKING_LABEL,
    FMGE_PATTERN,
    NEET_PG_PATTERN,
    UPSC_CMS_PATTERN,
} from '@/lib/examPatterns';

/**
 * Side-by-side comparisons between medical exams. Each entry ships as a
 * complete ComparisonContent ready to render via ComparisonLayout.
 *
 * Only comparisons that have a route are kept here; pattern facts come from
 * lib/examPatterns.ts and every /blog link must be an existing post slug.
 */

export const CMS_VS_NEETPG: ComparisonContent = {
    examASlug: 'cms',
    examBSlug: 'neet-pg',
    examAName: 'UPSC CMS',
    examBName: 'NEET PG',
    examALandingPath: '/cms',
    examBLandingPath: '/neet-pg',
    path: '/cms/vs-neet-pg',
    description: `UPSC CMS vs NEET PG — side-by-side comparison of exam pattern (${UPSC_CMS_PATTERN.totalQuestions} vs ${NEET_PG_PATTERN.totalQuestions} questions), negative marking (one-third vs −${NEET_PG_PATTERN.penaltyPerWrong} of +${NEET_PG_PATTERN.marksPerQuestion}), total marks (${UPSC_CMS_PATTERN.totalMarks} vs ${NEET_PG_PATTERN.totalMarks}), salary, difficulty, success rate, and which one to pick based on your career goals.`,
    verdict: 'UPSC CMS and NEET PG are both postgraduate medical exams but for different career tracks. CMS leads to central government medical officer roles; NEET PG leads to MD/MS specialisation.',
    chooseA: [
        'You want a central government medical officer position (Railways, CHS, ESIC)',
        'You prefer a non-clinical / administrative career path',
        'You want to settle early with a stable gazetted post',
        'You do not want to do a 3-year residency',
    ],
    chooseB: [
        'You want a clinical MD/MS in a specific branch (Medicine, Surgery, Radio, Anaesthesia)',
        'You want to become a superspecialist later (DM/MCh)',
        'You are willing to invest 3 years of residency for a clinical career',
        'You want private practice + hospital consultant track',
    ],
    rows: [
        { label: 'Conducting body', examA: 'UPSC', examB: 'NBE' },
        { label: 'Frequency', examA: 'Once a year', examB: 'Once a year' },
        { label: 'Pattern', examA: `2 papers × ${UPSC_CMS_PATTERN.papers[0].questions} Qs = ${UPSC_CMS_PATTERN.totalQuestions} Qs (${UPSC_CMS_PATTERN.modeShort})`, examB: `${NEET_PG_PATTERN.totalQuestions} Qs (single paper, CBT)` },
        { label: 'Negative marking', examA: `Yes — one-third of the question's marks (${CMS_MARKING_LABEL})`, examB: `Yes (−${NEET_PG_PATTERN.penaltyPerWrong} per wrong answer, +${NEET_PG_PATTERN.marksPerQuestion} per correct)` },
        { label: 'Total marks (written)', examA: `${UPSC_CMS_PATTERN.writtenMarks} (${UPSC_CMS_PATTERN.papers[0].marks} + ${UPSC_CMS_PATTERN.papers[1].marks})`, examB: `${NEET_PG_PATTERN.totalMarks} (${NEET_PG_PATTERN.marksPerQuestion} marks × ${NEET_PG_PATTERN.totalQuestions} Qs)` },
        { label: 'Final score', examA: `${UPSC_CMS_PATTERN.writtenMarks} written + ${UPSC_CMS_PATTERN.personalityTestMarks} Personality Test = ${UPSC_CMS_PATTERN.totalMarks}`, examB: `${NEET_PG_PATTERN.totalMarks} (only written, no interview)` },
        { label: 'Time', examA: '2 hours per paper', examB: '3.5 hours' },
        { label: 'Subjects', examA: 'Medicine, Surgery, Paediatrics, OBG, PSM + minor', examB: 'All 19 pre-clinical, para-clinical and clinical subjects' },
        { label: 'Difficulty', examA: 'Moderate (clinic-heavy, less depth)', examB: 'Hard (depth + breadth across 19 subjects)' },
        { label: 'Success rate', examA: '~1-3% of applicants qualify', examB: '~50% qualify for counselling, ~10% get top branch' },
        { label: 'Outcome', examA: 'MO / CHS / GDMO post (₹80k-₹1.2L in-hand)', examB: 'MD/MS seat (₹70k-₹1.5L stipend during residency, then 5-30L private)' },
        { label: 'Career ceiling', examA: 'Add. Director General, DGHS, CMOs', examB: 'Prof, HOD, superspecialist, hospital consultant' },
        { label: 'Preparation time', examA: '6 months typical', examB: '12-18 months typical' },
    ],
    faqs: [
        { q: 'Which is harder, UPSC CMS or NEET PG?', a: `NEET PG is broader (19 subjects, ${NEET_PG_PATTERN.totalMarks} marks, ${NEET_PG_PATTERN.totalQuestions} Qs in one go) and considered harder for most candidates. UPSC CMS is clinic-focused (${UPSC_CMS_PATTERN.totalQuestions} Qs across 2 papers) and easier to cover in 6 months.` },
        { q: 'Can I prepare for UPSC CMS and NEET PG together?', a: 'Yes — the two exams overlap ~70% in syllabus. Most candidates use NEET PG prep as a base and add UPSC-CMS-specific PSM and Surgery depth.' },
        { q: 'Which pays more, UPSC CMS or NEET PG?', a: 'NEET PG leads to clinical specialisation with much higher long-term earnings (₹20L-₹1Cr+ private practice). UPSC CMS gives a stable ₹80k-₹1.2L government salary from day one.' },
        { q: 'Should I attempt UPSC CMS if I already qualified NEET PG?', a: 'If you want a clinical career, take the MD/MS seat. If you want a stable government post without 3 years of residency, attempt UPSC CMS the same year — both exams are around 6 months apart.' },
    ],
    relatedLinks: [
        { label: 'UPSC CMS Preparation Guide 2026', href: '/cms' },
        { label: 'NEET PG Preparation Guide 2026', href: '/neet-pg' },
        { label: 'NEET PG vs UPSC CMS: Which Should You Choose? (Blog)', href: '/blog/neet-pg-vs-upsc-cms' },
        { label: 'UPSC CMS 2024 Cutoff (Category-wise)', href: '/blog/upsc-cms-2024-cutoff-marks-category-wise' },
        { label: 'NEET PG 2024 Cutoff (Category-wise)', href: '/blog/neet-pg-2024-cutoff-category-wise' },
        { label: 'Last Week Shared Revision: CMS + NEET PG', href: '/blog/cms-and-neet-pg-last-week-shared-revision' },
        { label: 'Best PG Medical Entrance Books', href: '/blog/best-pg-medical-entrance-books' },
        { label: 'UPSC CMS High-Yield Topics', href: '/blog/upsc-cms-syllabus-high-yield-topics' },
    ],
};

export const NEETPG_VS_USMLE: ComparisonContent = {
    examASlug: 'neet-pg',
    examBSlug: 'usmle',
    examAName: 'NEET PG',
    examBName: 'USMLE',
    examALandingPath: '/neet-pg',
    examBLandingPath: '/usmle',
    path: '/neet-pg/vs-usmle',
    description: 'NEET PG vs USMLE — exam pattern, prep time, cost, career path, and which one to pick as an Indian MBBS graduate. Step 1, Step 2 CK, and residency matching compared.',
    verdict: 'NEET PG is for Indian PG seats (₹2-15L total cost, 12-18 month prep). USMLE leads to US residency (₹15-25L total cost, 18-30 month prep) but requires navigating the Match process with ~50% success for IMGs.',
    chooseA: [
        'You want to specialise and practise in India',
        'You have financial constraints (USMLE prep + residency applications are expensive)',
        'You want a faster path to PG',
        'You want to be close to family',
    ],
    chooseB: [
        'You want to practise in the US',
        'You can afford ₹15-25L in prep + application costs',
        'You have strong USMLE scores (Step 1 pass + Step 2 CK ≥250)',
        'You want global research + clinical exposure',
    ],
    rows: [
        { label: 'Country', examA: 'India', examB: 'United States' },
        { label: 'Conducting body', examA: 'NBE', examB: 'NBME / FSMB / ECFMG' },
        { label: 'Pattern', examA: '200 Qs, single paper, 210 min', examB: 'Step 1: pass/fail (approx. 8h); Step 2 CK: ~320 Qs (9h)' },
        { label: 'Negative marking', examA: `Yes (−${NEET_PG_PATTERN.penaltyPerWrong} per wrong)`, examB: 'No (Step 1 pass/fail; Step 2 CK no negative marking)' },
        { label: 'Prep time', examA: '12-18 months', examB: '18-30 months' },
        { label: 'Total cost', examA: '₹2-15L (incl. coaching)', examB: '₹15-25L (incl. travel, ECFMG, applications)' },
        { label: 'Outcome', examA: 'MD/MS seat in India', examB: 'US residency match (ACGME program)' },
        { label: 'Residency duration', examA: '3 years', examB: '3-7 years (depends on specialty)' },
        { label: 'Salary after residency', examA: '₹10L-₹1Cr+ private', examB: '₹$180k-500k (₹1.5-4.2Cr) US average' },
        { label: 'Practice location', examA: 'India', examB: 'USA, then optional return' },
    ],
    faqs: [
        { q: 'Is USMLE harder than NEET PG?', a: 'Step 1 became pass/fail in January 2022 — there is no numeric score. USMLE tests applied clinical reasoning, while NEET PG tests depth across 19 subjects. Matching into a US residency as an IMG is the real challenge (~50% match rate).' },
        { q: 'Should Indian MBBS students attempt USMLE?', a: 'If you can afford ₹15-25L, have strong academics, and want global exposure, USMLE is worth it. NEET PG remains the practical choice for most Indian graduates seeking MD/MS seats.' },
        { q: 'Can I prepare for USMLE and NEET PG together?', a: 'Yes — pre-clinical and clinical subjects overlap heavily. Many Indian aspirants use First Aid + UWorld for USMLE while solving NEET PG MCQs alongside.' },
    ],
    relatedLinks: [
        { label: 'NEET PG Preparation Guide 2026', href: '/neet-pg' },
        { label: 'USMLE Step 1 Guide', href: '/guides/usmle-step-1-guide' },
        { label: 'NEET PG Preparation Strategy & Study Plans', href: '/blog/neet-pg-preparation-strategy-study-plans' },
        { label: 'NEET PG vs Other Exams', href: '/blog/neet-pg-comedk-mss-nursing-exams-comparison' },
        { label: 'Mock Test Analysis Guide', href: '/blog/mock-test-analysis-upsc-cms' },
        { label: 'Best PG Medical Entrance Books', href: '/blog/best-pg-medical-entrance-books' },
    ],
};

export const FMGE_VS_NEXT: ComparisonContent = {
    examASlug: 'fmge',
    examBSlug: 'next',
    examAName: 'FMGE',
    examBName: 'NEXT',
    examALandingPath: '/fmge',
    // NEXT has no landing page yet; NEET PG is the PG-entrance exam it is meant to replace.
    examBLandingPath: '/neet-pg',
    path: '/fmge/vs-next',
    description: 'FMGE vs NEXT — what changes for Indian students who completed MBBS abroad. Comparison of pattern, eligibility, negative marking, and career impact.',
    verdict: 'FMGE is the current licensing exam for foreign MBBS graduates (300 Qs in two parts, no negative marking). NEXT (National Exit Test) will eventually replace FMGE as a combined licensing + PG entrance exam, but the rollout has been delayed. As of 2026, FMGE remains the mandatory screening exam.',
    chooseA: [
        'You are graduating or have already graduated from a foreign MBBS programme',
        'You need the Screening Test to register with the NMC',
        'You want a single exam focused on licensing (not combined with PG ranking)',
    ],
    chooseB: [
        'You want ONE exam that serves both as a license and PG entrance',
        'You want a competency-based assessment (not pure MCQ-based)',
        'You are in an early year of MBBS abroad and can plan for the transition',
    ],
    rows: [
        { label: 'Conducting body', examA: 'NBE (on behalf of NMC)', examB: 'NMC / NBE (planned)' },
        { label: 'Pattern', examA: `${FMGE_PATTERN.totalQuestions} Qs in ${FMGE_PATTERN.parts} parts of ${FMGE_PATTERN.questionsPerPart} (${FMGE_PATTERN.minutesPerPart} min each), CBT`, examB: 'Single computer-based exam with multiple sections' },
        { label: 'Negative marking', examA: 'No negative marking', examB: 'No negative marking (proposed)' },
        { label: 'Frequency', examA: 'Twice a year (June + December)', examB: 'Expected twice a year (not confirmed)' },
        { label: 'Pass mark', examA: `${FMGE_PATTERN.passMarks}/${FMGE_PATTERN.totalQuestions} (50%)`, examB: 'Competency-based threshold (not defined yet)' },
        { label: 'Outcome', examA: 'License to practise in India + internship', examB: 'License to practise + PG entrance rank' },
        { label: 'Eligibility', examA: 'Foreign MBBS graduates with ECFMG equivalency', examB: 'All MBBS graduates (Indian + foreign)' },
        { label: 'Internship', examA: '12-month Indian internship required before practice', examB: 'Likely integrated into exam structure' },
    ],
    faqs: [
        { q: 'Is FMGE being replaced by NEXT?', a: 'Yes, NEXT is planned to replace FMGE for foreign graduates and will also serve as the PG entrance exam replacing NEET PG. However, the rollout has faced repeated delays. As of 2026, FMGE remains the active exam.' },
        { q: 'Should I still prepare for FMGE if NEXT is coming?', a: 'Absolutely — until NEXT is officially implemented, FMGE is the only way for foreign graduates to get licensed in India. Your FMGE preparation overlaps heavily with NEXT preparation (clinical subjects, preventive medicine).' },
        { q: 'What is the FMGE pass rate?', a: 'FMGE pass rate hovers around 15-25%, making it a challenging exam. NEXT, when implemented, is expected to have a more structured competency-based approach.' },
    ],
    relatedLinks: [
        { label: 'FMGE Exam Guide', href: '/fmge' },
        { label: 'FMGE Complete Guide', href: '/guides/fmge-complete-guide' },
        { label: 'Best PG Medical Entrance Books', href: '/blog/best-pg-medical-entrance-books' },
        { label: 'Time Management in the Exam Hall', href: '/blog/time-management-upsc-cms-paper' },
    ],
};
