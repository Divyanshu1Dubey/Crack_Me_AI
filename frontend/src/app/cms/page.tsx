import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';

const content: ExamLandingContent = {
    slug: 'cms',
    name: 'UPSC CMS',
    fullName: 'Combined Medical Services Examination',
    title: 'UPSC CMS Preparation 2026 — AI Tutor, PYQs, Mock Tests | CrackCMS',
    description: 'Prepare for UPSC CMS 2026 with 1,920+ previous year questions, AI-powered explanations, full mock tests and a CMS exam simulator. CrackCMS is the highest-rated CMS prep platform.',
    tagline: 'Crack the Combined Medical Services exam with the most-trusted AI tutor, 1,920+ PYQs, and full UPSC CMS mock test series.',
    heroBullets: [
        '1,920+ previous-year UPSC CMS questions (2009-2024)',
        'AI tutor that explains every answer with mnemonics & textbook references',
        'Real-exam simulator with negative marking (-0.33) and 120-min countdown',
        'Personalised analytics — see exactly which topics are dragging your rank',
    ],
    stats: [
        { number: '1,920+', label: 'UPSC CMS PYQs' },
        { number: '4.8/5', label: 'User rating' },
        { number: '47k+', label: 'Active aspirants' },
        { number: '11+', label: 'AI providers' },
    ],
    pattern: [
        { label: 'Papers', value: 'Paper I + Paper II' },
        { label: 'Total questions', value: '240 (120 + 120)' },
        { label: 'Time allowed', value: '120 minutes per paper' },
        { label: 'Marks per question', value: '4 marks' },
        { label: 'Negative marking', value: '-0.33 per wrong answer' },
        { label: 'Mode', value: 'Offline (pen-and-paper)' },
        { label: 'Subjects covered', value: 'Medicine, Surgery, Paediatrics, OBG, PSM, ENT, Ophthalmology, Anaesthesia, Orthopaedics' },
    ],
    eligibility: [
        { label: 'Nationality', value: 'Indian citizen (or subject of Nepal/Bhutan; Tibetan refugee with intent to settle in India)' },
        { label: 'Qualifying degree', value: 'MBBS (final year appearing or passed) from an NMC-recognised institution' },
        { label: 'Age limit', value: '32 years (relaxation for reserved categories per UPSC rules)' },
        { label: 'Attempts', value: 'No fixed limit; subject to age ceiling' },
        { label: 'Medical fitness', value: 'Must meet the physical/medical standards prescribed for the post applied for' },
    ],
    syllabus: [
        { subject: 'General Medicine', weight: 'High', topics: 'Cardiology, Respiratory, GI, Endocrinology, Neurology, Infectious diseases, Nephrology' },
        { subject: 'General Surgery', weight: 'High', topics: 'GI surgery, Trauma, Oncology, Burns, Hernia, Urology basics' },
        { subject: 'Paediatrics', weight: 'High', topics: 'Neonatology, Growth, Immunisation, Common childhood infections' },
        { subject: 'OBG', weight: 'High', topics: 'Antenatal care, High-risk pregnancy, Gynae oncology, Contraception' },
        { subject: 'PSM / Community Medicine', weight: 'High', topics: 'Epidemiology, Biostatistics, National health programmes, Nutrition' },
        { subject: 'ENT', weight: 'Medium', topics: 'Otitis, Sinusitis, Hearing loss, Vertigo' },
        { subject: 'Ophthalmology', weight: 'Medium', topics: 'Cataract, Glaucoma, Retina, Refractive errors' },
        { subject: 'Orthopaedics', weight: 'Medium', topics: 'Fractures, Bone tumours, Sports injuries' },
        { subject: 'Anaesthesia', weight: 'Low', topics: 'General & regional anaesthesia, CPR, Pain management' },
    ],
    books: [
        { name: 'Harrison\'s Principles of Internal Medicine', author: 'Loscalzo, Fauci, Kasper et al.', why: 'Gold standard for General Medicine. Use the latest 21st edition.' },
        { name: 'Bailey & Love\'s Short Practice of Surgery', author: 'Williams, O\'Connell, McCaskie', why: 'Definitive Surgery text. Pair with Manipal Manual of Surgery for MCQs.' },
        { name: 'OP Ghai Essential Pediatrics', author: 'Ghai, Paul, Bagga', why: 'Single-volume Paediatrics that covers the full UPSC CMS syllabus.' },
        { name: 'Park\'s Textbook of Preventive and Social Medicine', author: 'Park', why: 'Required for PSM and community medicine questions.' },
        { name: 'Dutta\'s Gynecology and Obstetrics', author: 'Dutta, Konar', why: 'Most-cited OBG textbook for Indian PG exams.' },
        { name: 'Review of Preventive & Social Medicine (Viva)', author: 'Vivek Jain', why: 'High-yield PSM MCQ book for last-mile revision.' },
    ],
    faqs: [
        { q: 'What is UPSC CMS?', a: 'UPSC CMS (Combined Medical Services) is an annual examination conducted by the Union Public Service Commission to recruit medical officers for central government services like the Central Health Service, Railways, Municipal Corporation of Delhi, and defence medical posts.' },
        { q: 'How many questions are in UPSC CMS?', a: 'UPSC CMS has two papers of 120 questions each (240 total), 4 marks per question, with 0.33 negative marking. Total marks per paper = 480.' },
        { q: 'What is the UPSC CMS 2026 syllabus?', a: 'The CMS syllabus covers General Medicine, Surgery, Paediatrics, OBG, Preventive & Social Medicine, ENT, Ophthalmology, Anaesthesia and Orthopaedics. See the table above for high-yield topics.' },
        { q: 'Who is eligible for UPSC CMS?', a: 'Any Indian citizen with an MBBS degree from an NMC-recognised college, aged under 32 (relaxations for SC/ST/OBC/PwD), may apply.' },
        { q: 'How many PYQs does CrackCMS have for UPSC CMS?', a: 'CrackCMS hosts 1,920+ previous-year UPSC CMS questions from 2009 to 2024, with AI-powered explanations, mnemonics, textbook references and similar-PYQ links.' },
        { q: 'Can I attempt a free UPSC CMS mock test on CrackCMS?', a: 'Yes — every account starts with 10 daily AI tokens and unlimited mock tests. Premium users unlock AI explanations and the exam simulator.' },
        { q: 'Does CrackCMS follow the latest UPSC CMS exam pattern?', a: 'Yes. Our mock tests use the latest two-paper, 240-question, 0.33-negative-marking format with a 120-minute countdown timer.' },
        { q: 'How should I prepare for UPSC CMS in 6 months?', a: 'Start with subject-wise PYQs to build a baseline, take one full mock every Sunday, spend 30 minutes daily on AI tutor for weak topics, and revise mnemonics using our spaced-repetition flashcards.' },
    ],
    accentFrom: 'from-indigo-600',
    accentTo: 'to-violet-700',
    emoji: '🏛️',
    pyqCount: '1,920+',
};

export const metadata = buildExamMetadata(content);

export default function CMSPage() {
    return ExamLandingLayout(content);
}
