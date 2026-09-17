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

export const NEETPG_VS_UPSC_CMS: ComparisonContent = {
    examASlug: 'neet-pg',
    examBSlug: 'cms',
    examAName: 'NEET PG',
    examBName: 'UPSC CMS',
    examALandingPath: '/neet-pg',
    examBLandingPath: '/cms',
    description: 'NEET PG vs UPSC CMS: Which exam should you choose after MBBS? Compare syllabus overlap, difficulty, salary, career growth, exam pattern, and which one matches your goals.',
    verdict: 'NEET PG leads to MD/MS clinical specialisation with higher long-term earnings. UPSC CMS leads to a central government Medical Officer post with stable salary and job security from day one. Both exams overlap ~70% in syllabus — most candidates attempt both.',
    chooseA: [
        'You want a clinical MD/MS in a specific branch (Medicine, Surgery, Radiology, Anaesthesia)',
        'You want to become a superspecialist later (DM/MCh)',
        'You are willing to invest 3 years of residency for long-term growth',
        'You want private practice or hospital consultant track',
    ],
    chooseB: [
        'You want a stable central government medical officer post (Railways, CHS, ESIC)',
        'You prefer a non-clinical or administrative career path',
        'You want work-life balance from day one without 3 years of residency',
        'You value job security, pension, and government perks',
    ],
    rows: [
        { label: 'Conducting body', examA: 'NBE', examB: 'UPSC' },
        { label: 'Frequency', examA: 'Once a year', examB: 'Once a year' },
        { label: 'Pattern', examA: '200 MCQs, single paper, 3.5 hours, 800 marks', examB: '240 MCQs, 2 papers, 2 hrs each, 960 marks' },
        { label: 'Negative marking', examA: 'No', examB: 'Yes (-0.33 per wrong answer)' },
        { label: 'Mode', examA: 'CBT', examB: 'Offline (pen-and-paper OMR)' },
        { label: 'Subjects', examA: 'All 19 pre-clinical, para-clinical, clinical subjects', examB: 'Medicine, Surgery, Paediatrics, OBG, PSM + minor subjects' },
        { label: 'Difficulty', examA: 'Hard (breadth across 19 subjects)', examB: 'Moderate (clinic-heavy, less depth)' },
        { label: 'Outcome', examA: 'MD/MS seat (residency)', examB: 'Medical Officer / GDMO post' },
        { label: 'Starting income', examA: '₹70k-₹1L stipend during 3-year residency', examB: '₹80k-₹1.2L from day one' },
        { label: 'Long-term earnings', examA: '₹20L-₹1Cr+ (private practice)', examB: '₹1.5L-₹2L (govt scale)' },
        { label: 'Career ceiling', examA: 'Prof, HOD, superspecialist, hospital consultant', examB: 'CMO, ADG, DGHS' },
        { label: 'Prep time', examA: '12-18 months typical', examB: '6 months typical' },
    ],
    faqs: [
        { q: 'Which is better, NEET PG or UPSC CMS?', a: 'It depends on your career goals. NEET PG is better if you want clinical MD/MS specialisation and long-term earning potential. UPSC CMS is better if you want a stable government job with work-life balance from day one without spending 3 years in residency.' },
        { q: 'Can I prepare for NEET PG and UPSC CMS together?', a: 'Yes — the two exams overlap ~70% in syllabus. Most candidates use NEET PG prep as a base and add UPSC-CMS-specific PSM and Surgery depth. Both exams are around 6 months apart, allowing back-to-back attempts.' },
        { q: 'Which pays more, NEET PG or UPSC CMS?', a: 'NEET PG leads to clinical specialisation with much higher long-term earnings (₹20L-₹1Cr+ in private practice). UPSC CMS gives a stable ₹80k-₹1.2L government salary from day one with excellent job security and pension benefits.' },
        { q: 'Is UPSC CMS tougher than NEET PG?', a: 'NEET PG is generally considered harder because of its breadth (19 subjects, 200 Qs in one sitting). UPSC CMS is clinic-focused (240 Qs across 2 papers) and can be covered in 6 months with focused preparation.' },
    ],
};

export const NEETPG_VS_INICET: ComparisonContent = {
    examASlug: 'neet-pg',
    examBSlug: 'ini-cet',
    examAName: 'NEET PG',
    examBName: 'INI-CET',
    examALandingPath: '/neet-pg',
    examBLandingPath: '/ini-cet',
    description: 'NEET PG vs INI-CET — which PG entrance exam is right for you? Compare pattern, difficulty, negative marking, seats, stipend, institutes (AIIMS/PGI/JIPMER vs all India), and preparation strategy.',
    verdict: 'NEET PG opens MD/MS seats across all medical colleges in India (~10,000+ seats). INI-CET opens PG seats only at AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST (~1,000-1,500 seats) but with higher brand value. Syllabus is ~80% overlapping. Most serious candidates attempt both.',
    chooseA: [
        'You want MD/MS seats across all medical colleges (including private and state)',
        'You prefer a broader, more predictable exam pattern',
        'You want counselling through MCC (centralised all-India counselling)',
        'You are targeting a specific branch and want maximum seat options',
    ],
    chooseB: [
        'You want a PG seat at AIIMS, PGI, JIPMER, NIMHANS, SCTIMST',
        'You thrive on conceptual, image-based questions',
        'You want the prestige and research opportunities of central institutes',
        'You want two chances per year (January + July sessions)',
    ],
    rows: [
        { label: 'Conducting body', examA: 'NBE', examB: 'AIIMS New Delhi' },
        { label: 'Frequency', examA: 'Once a year (June)', examB: 'Twice a year (Jan + July)' },
        { label: 'Questions', examA: '200 MCQs, 3.5 hours', examB: '200 MCQs, 3 hours' },
        { label: 'Negative marking', examA: 'No', examB: 'Yes (-1/3 per wrong answer)' },
        { label: 'Total marks', examA: '800', examB: '200' },
        { label: 'Mode', examA: 'CBT', examB: 'CBT' },
        { label: 'Institutes', examA: 'All medical colleges in India', examB: 'AIIMS, PGI, JIPMER, NIMHANS, SCTIMST only' },
        { label: 'Seats', examA: '~10,000+ MD/MS seats', examB: '~1,000-1,500 PG seats' },
        { label: 'Difficulty', examA: 'Hard (breadth across 19 subjects)', examB: 'Harder (depth + image-based + -1/3)' },
        { label: 'Stipend', examA: '₹70k-₹1L/month', examB: '₹90k-₹1.1L/month' },
    ],
    faqs: [
        { q: 'Which is tougher, NEET PG or INI-CET?', a: 'INI-CET is generally considered slightly tougher due to deeper clinical reasoning, image-based questions, and -1/3 negative marking. NEET PG is broader but has more memory-based questions and no negative marking.' },
        { q: 'Is INI-CET and NEET PG syllabus same?', a: 'Yes — both cover the same 19 pre-clinical, para-clinical and clinical subjects. INI-CET questions tend to be more conceptual and image-based, while NEET PG has more direct recall questions.' },
        { q: 'Can I appear for both NEET PG and INI-CET?', a: 'Yes — NEET PG is once yearly (June), INI-CET is twice yearly (Jan + July). Many serious candidates attempt both to maximise PG seat options. The syllabus is ~80% overlapping.' },
        { q: 'Which institutes are under INI-CET?', a: 'INI-CET is the common entrance for AIIMS (all campuses), PGIMER Chandigarh, JIPMER Puducherry, NIMHANS Bangalore, and SCTIMST Trivandrum.' },
    ],
};

export const ALL_COMPARISONS: Record<string, ComparisonContent> = {
    'cms/vs-neet-pg': CMS_VS_NEETPG,
    'cms/vs-ini-cet': CMS_VS_INICET,
    'neet-pg/vs-usmle': NEETPG_VS_USMLE,
    'neet-pg/vs-ini-cet': NEETPG_VS_INICET,
    'neet-pg/vs-upsc-cms': NEETPG_VS_UPSC_CMS,
    'fmge/vs-next': FMGE_VS_NEXT,
};