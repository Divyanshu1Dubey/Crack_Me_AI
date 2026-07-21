import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';

const content: ExamLandingContent = {
    slug: 'neet-pg',
    name: 'NEET PG',
    fullName: 'National Eligibility cum Entrance Test (Postgraduate)',
    title: 'NEET PG Preparation 2026 — PYQs, Mock Tests, AI Tutor | CrackCMS',
    description: 'Crack NEET PG 2026 with 18,000+ previous year MCQs, AI explanations, clinical case simulations, and full mock tests. Highest-rated NEET PG prep platform.',
    tagline: 'India\'s most comprehensive NEET PG preparation platform — 18,000+ PYQs across all 19 subjects, AI tutor, and All-India rank predictor.',
    heroBullets: [
        '18,000+ NEET PG MCQs across all 19 clinical & para-clinical subjects',
        'AI tutor trained on Harrison, Robbins, Bailey, Ghai, Park, Goodman & Gilman',
        'Real-time All-India Rank prediction after every mock',
        'Spaced-repetition flashcards that adapt to your weak areas',
    ],
    stats: [
        { number: '18,000+', label: 'NEET PG MCQs' },
        { number: '4.8/5', label: 'User rating' },
        { number: '47k+', label: 'Active aspirants' },
        { number: 'AIR rank', label: 'Predictor after every test' },
    ],
    pattern: [
        { label: 'Mode', value: 'Computer-Based Test (CBT)' },
        { label: 'Total questions', value: '200 MCQs' },
        { label: 'Time allowed', value: '210 minutes (3.5 hours)' },
        { label: 'Marks per question', value: '4 marks' },
        { label: 'Negative marking', value: '-1 per wrong answer' },
        { label: 'Total marks', value: '800' },
        { label: 'Subject distribution', value: 'Pre-clinical, Para-clinical, and Clinical subjects as per NBE syllabus' },
    ],
    eligibility: [
        { label: 'Qualifying degree', value: 'MBBS from an NMC-recognised college (or provisional MBBS pass certificate)' },
        { label: 'Internship', value: 'Completed or completing the 12-month compulsory rotating internship by the cutoff date' },
        { label: 'NMC registration', value: 'Provisional or permanent registration certificate issued by NMC / State Medical Council' },
        { label: 'Nationality', value: 'Indian citizen, OCI, or foreign national (separate quota)' },
        { label: 'No upper age limit', value: 'Supreme Court struck down the age-cap in 2023 (subject to NBE notification)' },
    ],
    syllabus: [
        { subject: 'Pre-clinical: Anatomy, Physiology, Biochemistry', weight: '~20%', topics: 'High-yield Neuroanatomy, Endocrine physiology, Enzymes, Metabolism' },
        { subject: 'Para-clinical: Pathology, Pharmacology, Microbiology, Forensic Medicine, Community Medicine', weight: '~30%', topics: 'Neoplasia, Autonomic pharmacology, Antimicrobials, PSM, Biostatistics' },
        { subject: 'Clinical: Medicine & Allied', weight: '~25%', topics: 'Cardiology, Neurology, Endocrinology, Respiratory, GI' },
        { subject: 'Clinical: Surgery & Allied', weight: '~15%', topics: 'GI surgery, Urology, Orthopaedics, Anaesthesia' },
        { subject: 'OBG, Paediatrics, Ophthalmology, ENT', weight: '~10%', topics: 'High-yield obstetrics, Neonatology, Glaucoma, Otitis media' },
        { subject: 'Image-based questions', weight: 'Bonus', topics: 'CT, MRI, X-ray, Histopathology slides (recently added by NBE)' },
    ],
    books: [
        { name: 'Harrison\'s Principles of Internal Medicine', author: 'Fauci, Loscalzo, Kasper et al.', why: 'Bible of Medicine — most clinical NEET PG questions are referenced from Harrison.' },
        { name: 'Robbins Pathologic Basis of Disease', author: 'Kumar, Abbas, Aster', why: 'Pathology standard. Pair with Robbins Review Questions for MCQ practice.' },
        { name: 'Bailey & Love + Manipal Manual of Surgery', author: 'Williams / Shenoy', why: 'Complete Surgery prep — Bailey for concepts, Manipal for MCQ patterns.' },
        { name: 'Review of Pharmacology (KD Tripathi)', author: 'Tripathi', why: 'Concise Pharmacology with diagram-based drug classifications.' },
        { name: 'DCR (Dutta) + Shaw\'s Textbook of Gynaecology', author: 'Dutta / Shaw', why: 'Best OBG combo for NEET PG.' },
        { name: 'OP Ghai + IAP Textbook of Pediatrics', author: 'Ghai / IAP', why: 'Pediatrics standard references for Indian PG exams.' },
    ],
    faqs: [
        { q: 'What is NEET PG?', a: 'NEET PG (National Eligibility cum Entrance Test - Post Graduate) is the single-window entrance examination for MD/MS/PG Diploma courses in India, conducted by the National Board of Examinations (NBE).' },
        { q: 'How many questions are in NEET PG 2026?', a: 'NEET PG has 200 MCQs across pre-clinical, para-clinical, and clinical subjects. Total marks: 800. Time: 210 minutes.' },
        { q: 'Is there negative marking in NEET PG?', a: 'Yes. Each wrong answer attracts -1 mark. Unanswered questions carry 0.' },
        { q: 'Who conducts NEET PG?', a: 'The National Board of Examinations (NBE), an autonomous body under the Ministry of Health & Family Welfare, Government of India.' },
        { q: 'What is the NEET PG 2026 syllabus?', a: 'The syllabus covers MBBS-level pre-clinical, para-clinical, and clinical subjects as prescribed by the NMC. Image-based questions were introduced in recent years.' },
        { q: 'How should I start NEET PG preparation?', a: 'Begin with a subject-wise baseline using previous-year MCQs, identify weak topics with our analytics, schedule 2 full mocks per week, and use AI tutor for concept gaps.' },
        { q: 'Can CrackCMS predict my All-India Rank?', a: 'Yes. After every mock test, our rank predictor uses historical NBE cutoffs to estimate your AIR based on your score and category.' },
        { q: 'Does CrackCMS have NEET PG image-based questions?', a: 'Yes — we curate image-based MCQs (radiology, histopathology, dermatology) tagged separately so you can drill them in dedicated sessions.' },
    ],
    accentFrom: 'from-emerald-600',
    accentTo: 'to-teal-700',
    emoji: '🩺',
    pyqCount: '18,000+',
};

export const metadata = buildExamMetadata(content);

export default function NEETPGPage() {
    return ExamLandingLayout(content);
}
