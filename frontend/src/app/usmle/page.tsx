import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';

const content: ExamLandingContent = {
    slug: 'usmle',
    name: 'USMLE',
    fullName: 'United States Medical Licensing Examination',
    title: 'USMLE Step 1 Preparation — AI Tutor, First Aid MCQs, NBME Bank | CrackCMS',
    description: 'Crack USMLE Step 1 with First Aid-aligned MCQs, AI tutor, NBME-pattern mock tests. Designed for Indian medical students targeting US residency.',
    tagline: 'Crack USMLE Step 1 with First Aid-aligned MCQs, AI tutor, NBME-pattern mocks, and high-yield flashcards.',
    heroBullets: [
        '10,000+ USMLE Step 1 MCQs aligned with First Aid 2025',
        'AI tutor explains with First Aid + Pathoma + UWorld style rationales',
        'NBME-style practice blocks (40 questions, 60-min timed)',
        'High-yield flashcards auto-generated from your weak areas',
    ],
    stats: [
        { number: '10,000+', label: 'USMLE Step 1 MCQs' },
        { number: '4.8/5', label: 'User rating' },
        { number: '47k+', label: 'Active aspirants' },
        { number: 'First Aid', label: 'Aligned content' },
    ],
    pattern: [
        { label: 'Step 1 structure', value: '280 MCQs across 7 blocks (40 questions each)' },
        { label: 'Time per block', value: '60 minutes (with 45 min break)' },
        { label: 'Total time', value: '8 hours (including breaks)' },
        { label: 'Question formats', value: 'Single-best-answer, multi-step, abstract, video, audio' },
        { label: 'Scoring', value: 'Pass/Fail (since January 2022); numeric score reported on request' },
        { label: 'Eligibility', value: 'Medical student or graduate of an LCME / foreign-listed medical school' },
    ],
    eligibility: [
        { label: 'Medical school', value: 'Enrolled in or graduated from an LCME-accredited US/Canadian school OR a foreign school listed in WDOMS' },
        { label: 'ECFMG certification', value: 'Required for IMGs before residency match (USMLE Step 1 + Step 2 CK + OET)' },
        { label: 'No age limit', value: 'Apply any time after completing basic science coursework' },
        { label: 'Attempt limit', value: 'Maximum 4 attempts per Step (effective 2024)' },
    ],
    syllabus: [
        { subject: 'Pathology', weight: 'High', topics: 'Cell injury, Inflammation, Neoplasia, Hemodynamic disorders' },
        { subject: 'Physiology', weight: 'High', topics: 'Cardiovascular, Respiratory, Renal, GI, Endocrine' },
        { subject: 'Pharmacology', weight: 'High', topics: 'Autonomic, CNS, Antimicrobials, Chemotherapeutics' },
        { subject: 'Biochemistry & Molecular Biology', weight: 'High', topics: 'Metabolism, Genetics, Nutrition' },
        { subject: 'Microbiology & Immunology', weight: 'High', topics: 'Bacteria, Viruses, Fungi, Parasites, Immune system' },
        { subject: 'Behavioral Science & Biostatistics', weight: 'Medium', topics: 'Epidemiology, Ethics, Patient safety' },
        { subject: 'Anatomy, Histology, Embryology', weight: 'Medium', topics: 'High-yield anatomy with clinical correlation' },
    ],
    books: [
        { name: 'First Aid for the USMLE Step 1', author: 'Le, Bhushan', why: 'Bible — use as your central checklist. Every CrackCMS USMLE question maps to a First Aid page.' },
        { name: 'Pathoma', author: 'Sattar', why: 'Best Pathology video + textbook resource for Step 1.' },
        { name: 'Sketchy Medical', author: 'Sketchy', why: 'Visual mnemonics for Microbiology, Pharmacology, and Pathology.' },
        { name: 'UWorld QBank', author: 'UWorld', why: 'Closest to the real exam. Use after finishing CrackCMS subject-wise MCQs.' },
        { name: 'Boards & Beyond', author: 'Ryan', why: 'Video lectures aligned with First Aid.' },
        { name: 'Rx Bricks', author: 'Lecturio', why: 'Conceptual building blocks for weak topics.' },
    ],
    faqs: [
        { q: 'What is USMLE Step 1?', a: 'USMLE Step 1 is the first of three exams required for medical licensure in the United States. It tests understanding of basic medical sciences with emphasis on principles and mechanisms.' },
        { q: 'How many questions in USMLE Step 1?', a: '280 MCQs across 7 blocks of 40 questions each. Each block is 60 minutes, total 8 hours including breaks.' },
        { q: 'Is USMLE Step 1 pass/fail?', a: 'Yes, since January 2022 USMLE Step 1 is pass/fail. Numeric scores are still reported to the examinee on request.' },
        { q: 'What is a good USMLE Step 1 score for IMGs?', a: 'For Indian medical graduates (IMGs) applying for US residency, Step 2 CK score carries more weight since Step 1 is pass/fail. A 240+ on Step 2 CK opens doors to most specialties.' },
        { q: 'How long should I study for USMLE Step 1?', a: 'Most IMGs study for 6-9 months alongside or after MBBS intern year. Dedicated study periods: 8-12 hours/day for 6-8 weeks.' },
        { q: 'Does CrackCMS replace UWorld?', a: 'No — UWorld is the gold standard. CrackCMS complements UWorld by providing First Aid-aligned explanations, AI tutor for concept gaps, and Indian-context clinical reasoning.' },
    ],
    accentFrom: 'from-purple-600',
    accentTo: 'to-indigo-700',
    emoji: '🇺🇸',
    pyqCount: '10,000+',
};

export const metadata = buildExamMetadata(content);

export default function USMLEPage() {
    return ExamLandingLayout(content);
}
