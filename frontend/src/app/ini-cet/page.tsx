import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';

const content: ExamLandingContent = {
    slug: 'ini-cet',
    name: 'INI-CET',
    fullName: 'Institute of National Importance - Combined Entrance Test',
    title: 'INI-CET Preparation 2026 — AIIMS, PGIMER, JIPMER, NIMHANS | CrackCMS',
    description: 'Crack INI-CET 2026 for AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST. PYQs, mock tests, AI tutor, and All-India rank prediction.',
    tagline: 'Crack INI-CET for AIIMS, PGIMER, JIPMER, NIMHANS and SCTIMST with AI tutor, 12,000+ PYQs, and All-India rank predictor.',
    heroBullets: [
        '12,000+ INI-CET PYQs spanning AIIMS, PGIMER, JIPMER, NIMHANS',
        'AI tutor that explains with mnemonics and clinical pearls',
        'Mock tests with the exact CBT interface used by AIIMS',
        'All-India rank prediction using historical AIIMS cutoffs',
    ],
    stats: [
        { number: '12,000+', label: 'INI-CET MCQs' },
        { number: '4.8/5', label: 'User rating' },
        { number: '47k+', label: 'Active aspirants' },
        { number: 'AIIMS', label: 'Pattern accuracy' },
    ],
    pattern: [
        { label: 'Mode', value: 'Computer-Based Test (CBT) - online' },
        { label: 'Total questions', value: '200 MCQs' },
        { label: 'Time allowed', value: '180 minutes (3 hours)' },
        { label: 'Marks per question', value: '1 mark' },
        { label: 'Negative marking', value: '-1/3 per wrong answer' },
        { label: 'Total marks', value: '200' },
        { label: 'Frequency', value: 'Twice a year (January and July sessions)' },
    ],
    eligibility: [
        { label: 'Qualifying degree', value: 'MBBS / BDS / equivalent from an NMC/DCI-recognised institution' },
        { label: 'Internship', value: '12-month compulsory rotating internship completed by the cutoff date' },
        { label: 'Registration', value: 'Permanent or provisional registration with NMC / State Medical Council' },
        { label: 'Indian citizenship', value: 'Required for AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST' },
    ],
    syllabus: [
        { subject: 'Pre-clinical', weight: '~15%', topics: 'Anatomy, Physiology, Biochemistry — high-yield topics only' },
        { subject: 'Para-clinical', weight: '~25%', topics: 'Pathology, Microbiology, Pharmacology, Forensic Medicine, PSM' },
        { subject: 'Medicine & Allied', weight: '~25%', topics: 'Cardiology, Neurology, Endocrinology, Respiratory, GI, Infectious diseases' },
        { subject: 'Surgery & Allied', weight: '~20%', topics: 'GI surgery, Urology, Orthopaedics, Anaesthesia' },
        { subject: 'OBG & Paediatrics', weight: '~15%', topics: 'Antenatal care, Gynae oncology, Neonatology, Common childhood diseases' },
    ],
    books: [
        { name: 'Harrison + AIIMS-PGI Surgery guide', author: 'Multiple authors', why: 'Best combo for INI-CET Medicine + Surgery.' },
        { name: 'AIIMS PG solved papers', author: 'Various publishers', why: 'Last 10 years of AIIMS papers with explanations — most relevant.' },
        { name: 'Self Assessment & Review of NEET/AIIMS Pattern', author: 'Arora', why: 'Single-volume MCQ book for revision.' },
        { name: 'PGI Chandigarh solved papers', author: 'Various', why: 'Pattern-setter for INI-CET.' },
    ],
    faqs: [
        { q: 'What is INI-CET?', a: 'INI-CET (Institute of National Importance - Combined Entrance Test) is the common entrance exam for PG medical courses at AIIMS, PGIMER Chandigarh, JIPMER Puducherry, NIMHANS Bangalore, and SCTIMST Trivandrum.' },
        { q: 'How many times is INI-CET held per year?', a: 'Twice a year — January session and July session. AIIMS conducts the test on behalf of all participating institutes.' },
        { q: 'How many questions in INI-CET?', a: '200 MCQs, 180 minutes, 1 mark each, -1/3 negative marking, total 200 marks.' },
        { q: 'Is INI-CET harder than NEET PG?', a: 'INI-CET questions test conceptual depth and image-based reasoning more than NEET PG. Cut-offs are typically higher relative to the candidate pool.' },
        { q: 'Can I appear for INI-CET while doing internship?', a: 'Yes, if your internship completes by the cutoff date mentioned in the January/July session information bulletin.' },
        { q: 'How should I prepare for INI-CET in 4 months?', a: 'Solve 5,000+ PYQs, take one full mock every Sunday, focus on image-based MCQs (radiology + histopath), and use AI tutor for clinical reasoning gaps.' },
        { q: 'Does CrackCMS have AIIMS image-based questions?', a: 'Yes — our INI-CET bank has a dedicated image-based filter for radiology, dermatology, and pathology slides.' },
    ],
    accentFrom: 'from-pink-600',
    accentTo: 'to-rose-700',
    emoji: '🏥',
    pyqCount: '12,000+',
};

export const metadata = buildExamMetadata(content);

export default function INICETPage() {
    return ExamLandingLayout(content);
}
