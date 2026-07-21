import type { ComparisonContent } from '@/components/ComparisonLayout';

/**
 * Side-by-side comparisons between medical exams. Each entry ships as a
 * complete ComparisonContent ready to render via ComparisonLayout.
 */

export const CMS_VS_NEETPG: ComparisonContent = {
    examASlug: 'cms',
    examBSlug: 'neet-pg',
    examAName: 'UPSC CMS',
    examBName: 'NEET PG',
    examALandingPath: '/cms',
    examBLandingPath: '/neet-pg',
    description: 'Side-by-side comparison of UPSC CMS and NEET PG — exam pattern, difficulty, syllabus, salary, and which one to pick based on your career goals.',
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
        { label: 'Pattern', examA: '2 papers × 120 Qs = 240 Qs', examB: '200 Qs (single paper, CBT)' },
        { label: 'Negative marking', examA: 'Yes (−0.33)', examB: 'No (no negative marking)' },
        { label: 'Total marks', examA: '960', examB: '800' },
        { label: 'Time', examA: '2 hours per paper', examB: '3.5 hours' },
        { label: 'Subjects', examA: 'Medicine, Surgery, Paediatrics, OBG, PSM + minor', examB: 'All 19 pre-clinical, para-clinical and clinical subjects' },
        { label: 'Difficulty', examA: 'Moderate (clinic-heavy, less depth)', examB: 'Hard (depth + breadth across 19 subjects)' },
        { label: 'Success rate', examA: '~1-3% of applicants qualify', examB: '~50% qualify for counselling, ~10% get top branch' },
        { label: 'Outcome', examA: 'MO / CHS / GDMO post (₹80k-₹1.2L in-hand)', examB: 'MD/MS seat (₹70k-₹1.5L stipend during residency, then 5-30L private)' },
        { label: 'Career ceiling', examA: 'Add. Director General, DGHS, CMOs', examB: 'Prof, HOD, superspecialist, hospital consultant' },
        { label: 'Preparation time', examA: '6 months typical', examB: '12-18 months typical' },
    ],
    faqs: [
        { q: 'Which is harder, UPSC CMS or NEET PG?', a: 'NEET PG is broader (19 subjects, 800 marks, 200 Qs in one go) and considered harder for most candidates. UPSC CMS is clinic-focused (240 Qs across 2 papers) and easier to cover in 6 months.' },
        { q: 'Can I prepare for UPSC CMS and NEET PG together?', a: 'Yes — the two exams overlap ~70% in syllabus. Most candidates use NEET PG prep as a base and add UPSC-CMS-specific PSM and Surgery depth.' },
        { q: 'Which pays more, UPSC CMS or NEET PG?', a: 'NEET PG leads to clinical specialisation with much higher long-term earnings (₹20L-₹1Cr+ private practice). UPSC CMS gives a stable ₹80k-₹1.2L government salary from day one.' },
        { q: 'Should I attempt UPSC CMS if I already qualified NEET PG?', a: 'If you want a clinical career, take the MD/MS seat. If you want a stable government post without 3 years of residency, attempt UPSC CMS the same year — both exams are around 6 months apart.' },
    ],
};

export const CMS_VS_INICET: ComparisonContent = {
    examASlug: 'cms',
    examBSlug: 'ini-cet',
    examAName: 'UPSC CMS',
    examBName: 'INI-CET',
    examALandingPath: '/cms',
    examBLandingPath: '/ini-cet',
    description: 'UPSC CMS vs INI-CET — pattern, salary, lifestyle, and which exam matches your career goals. Side-by-side comparison with FAQs.',
    verdict: 'UPSC CMS leads to central government medical officer posts; INI-CET leads to MD/MS seats at AIIMS, PGIMER, JIPMER, NIMHANS. Different career tracks with different lifestyles.',
    chooseA: [
        'You want a gazetted medical officer post without residency',
        'You prefer a non-clinical or administrative career',
        'You want work-life balance from day one',
        'You have not done a year of internship yet',
    ],
    chooseB: [
        'You want to specialise at AIIMS / PGI / JIPMER',
        'You want a clinical academic career',
        'You are willing to do 3 years of residency at a top central institute',
        'You want superspecialisation (DM/MCh) afterwards',
    ],
    rows: [
        { label: 'Conducting body', examA: 'UPSC', examB: 'AIIMS New Delhi' },
        { label: 'Frequency', examA: 'Once a year', examB: 'Twice a year (Jan + July)' },
        { label: 'Pattern', examA: '240 Qs, 2 papers, 120 min each', examB: '200 Qs, single paper, 180 min' },
        { label: 'Negative marking', examA: 'Yes (−0.33)', examB: 'Yes (−1)' },
        { label: 'Outcome', examA: 'MO / CHS / GDMO post', examB: 'MD/MS/MDS at AIIMS/PGI/JIPMER/NIMHANS' },
        { label: 'Salary during', examA: '₹80k-₹1.2L from day one', examB: '₹90k-₹1.1L stipend during residency' },
        { label: 'Post-residency', examA: 'Same as above', examB: 'Senior Resident ₹1.2-1.8L, then faculty track' },
        { label: 'Career ceiling', examA: 'Add. DG, DGHS, CMO', examB: 'Prof, HOD, Dean, Director AIIMS' },
        { label: 'Syllabus depth', examA: 'Clinic-heavy, 5 main subjects', examB: 'All 19 subjects, deeper' },
        { label: 'Cutoff difficulty', examA: 'Moderate', examB: 'High (limited AIIMS seats)' },
    ],
    faqs: [
        { q: 'Which is harder, UPSC CMS or INI-CET?', a: 'INI-CET is harder because of more negative marking (−1 vs −0.33), deeper syllabus, and limited seats at top central institutes.' },
        { q: 'Is INI-CET tougher than NEET PG?', a: 'INI-CET is generally considered slightly tougher due to deeper clinical reasoning and tighter negative marking, but the syllabus is the same as NEET PG.' },
        { q: 'Can I attempt UPSC CMS and INI-CET in the same year?', a: 'Yes — both happen around July-November, allowing back-to-back attempts. Many candidates use CMS as a backup if INI-CET does not yield a seat.' },
    ],
};

export const NEETPG_VS_USMLE: ComparisonContent = {
    examASlug: 'neet-pg',
    examBSlug: 'usmle',
    examAName: 'NEET PG',
    examBName: 'USMLE',
    examALandingPath: '/neet-pg',
    examBLandingPath: '/usmle',
    description: 'NEET PG vs USMLE Step 1 — exam pattern, prep time, cost, career path, and which one to pick as an Indian MBBS graduate.',
    verdict: 'NEET PG is for Indian PG seats (₹2-15L total cost, 12-18 month prep). USMLE Step 1 leads to US residency (₹15-25L total cost, 18-30 month prep, with the option to skip Step 2 CK matching separately).',
    chooseA: [
        'You want to specialise and practise in India',
        'You have financial constraints (USMLE prep + residency applications are expensive)',
        'You want a faster path to PG',
        'You want to be close to family',
    ],
    chooseB: [
        'You want to practise in the US',
        'You can afford ₹15-25L in prep + application costs',
        'You have a strong Step 1 score (240+) foundation',
        'You want global research + clinical exposure',
    ],
    rows: [
        { label: 'Country', examA: 'India', examB: 'United States' },
        { label: 'Conducting body', examA: 'NBE', examB: 'NBME / FSMB / ECFMG' },
        { label: 'Pattern', examA: '200 Qs, single paper, 210 min', examB: '~280 Qs across 7 blocks, 8 hours' },
        { label: 'Negative marking', examA: 'No', examB: 'No' },
        { label: 'Prep time', examA: '12-18 months', examB: '18-30 months' },
        { label: 'Total cost', examA: '₹2-15L (incl. coaching)', examB: '₹15-25L (incl. travel, applications)' },
        { label: 'Outcome', examA: 'MD/MS seat in India', examB: 'US residency match' },
        { label: 'Residency duration', examA: '3 years', examB: '3-7 years (depends on specialty)' },
        { label: 'Salary after residency', examA: '₹10L-₹1Cr private', examB: '₹$200k-700k (₹1.6-5.8Cr)' },
        { label: 'Practice location', examA: 'India', examB: 'USA, then optional return' },
    ],
    faqs: [
        { q: 'Is USMLE harder than NEET PG?', a: 'USMLE Step 1 is conceptually deeper and tests applied reasoning, not memorisation. The pass rate for IMGs is ~80% on Step 1, but matching into residency is harder (~50% match rate for IMGs).' },
        { q: 'Should Indian MBBS students attempt USMLE?', a: 'If you can afford it, have a Step 1 score of 240+, and want global clinical exposure, USMLE is worth it. Otherwise, NEET PG remains the practical choice.' },
        { q: 'Can I prepare for USMLE and NEET PG together?', a: 'Yes — pre-clinical and clinical subjects overlap heavily. Many Indian aspirants use First Aid + UWorld for USMLE while solving NEET PG MCQs alongside.' },
    ],
};

export const FMGE_VS_NEXT: ComparisonContent = {
    examASlug: 'fmge',
    examBSlug: 'neet-pg',
    examAName: 'FMGE',
    examBName: 'NEXT',
    examALandingPath: '/fmge',
    examBLandingPath: '/neet-pg',
    description: 'FMGE vs NEXT — what changes for Indian students who completed MBBS abroad after the NEXT rollout. Comparison of pattern, eligibility, and career impact.',
    verdict: 'FMGE is the current licensing exam for foreign MBBS graduates. NEXT will replace it as a combined licensing + PG entrance exam from 2025 onwards. Aspirants should prepare for NEXT-like MCQs from now.',
    chooseA: [
        'You are graduating from a foreign university before 2025',
        'You are ineligible or not yet ready for NEXT',
        'You are pursuing a non-clinical career',
    ],
    chooseB: [
        'You are starting MBBS abroad now (class of 2019+)',
        'You want to attempt the PG entrance alongside licensing',
        'You want a modernised competency-based exam',
    ],
    rows: [
        { label: 'Conducting body', examA: 'NBE', examB: 'NMC (proposed)' },
        { label: 'Pattern', examA: '300 Qs, 2 papers', examB: 'Single computer-based exam (multiple components)' },
        { label: 'Negative marking', examA: 'No', examB: 'No (proposed)' },
        { label: 'Frequency', examA: 'Twice a year (June, Dec)', examB: 'Likely twice a year' },
        { label: 'Pass mark', examA: '150/300 (50%)', examB: 'Likely competency-based' },
        { label: 'Outcome', examA: 'License to practise in India', examB: 'License + PG entrance rank' },
        { label: 'Eligibility', examA: 'Foreign MBBS graduates', examB: 'All MBBS graduates (Indian + foreign)' },
        { label: 'Internship requirement', examA: 'After clearing, do 12-month Indian internship', examB: 'Likely integrated into the exam structure' },
    ],
    faqs: [
        { q: 'Is FMGE being replaced by NEXT?', a: 'Yes — NEXT (National Exit Test) will replace FMGE for foreign graduates and will also serve as the PG entrance exam replacing NEET PG. Rollout is gradual, starting ~2025.' },
        { q: 'Should I still prepare for FMGE if NEXT is coming?', a: 'Yes — until NEXT is fully implemented, FMGE remains the licensing exam. NEXT preparation overlaps significantly (NextStep + Park + Harrison).' },
        { q: 'What is the FMGE pass rate?', a: 'FMGE pass rate is historically ~15-25%, making it one of the toughest Indian medical exams. NEXT is expected to have a more structured approach with competency-based assessment.' },
    ],
};

export const ALL_COMPARISONS: Record<string, ComparisonContent> = {
    'cms/vs-neet-pg': CMS_VS_NEETPG,
    'cms/vs-ini-cet': CMS_VS_INICET,
    'neet-pg/vs-usmle': NEETPG_VS_USMLE,
    'fmge/vs-next': FMGE_VS_NEXT,
};