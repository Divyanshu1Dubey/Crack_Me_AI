import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';

const content: ExamLandingContent = {
    slug: 'fmge',
    name: 'FMGE',
    fullName: 'Foreign Medical Graduate Examination',
    title: 'FMGE Preparation 2026 — MCI Screening Test for Foreign MBBS | CrackCMS',
    description: 'Crack FMGE 2026 (MCI Screening Test) with 8,000+ previous MCQs, AI tutor, mock tests and clinical case drills. The most-trusted FMGE prep platform for foreign MBBS graduates.',
    tagline: 'Pass FMGE on your first attempt with 8,000+ MCI-aligned MCQs, AI tutor, and full mock tests.',
    heroBullets: [
        '8,000+ FMGE-aligned MCQs covering all 19 subjects',
        'AI tutor trained on Indian medical textbooks',
        'Mock tests with the exact NBEMS CBT interface',
        'Personalised analytics to identify weak topics',
    ],
    stats: [
        { number: '8,000+', label: 'FMGE MCQs' },
        { number: '4.7/5', label: 'User rating' },
        { number: '47k+', label: 'Active aspirants' },
        { number: 'NBEMS', label: 'Aligned syllabus' },
    ],
    pattern: [
        { label: 'Mode', value: 'Computer-Based Test (CBT)' },
        { label: 'Total questions', value: '300 MCQs' },
        { label: 'Time allowed', value: '300 minutes (5 hours, two parts of 2.5 hours each)' },
        { label: 'Marks per question', value: '1 mark' },
        { label: 'Negative marking', value: 'None' },
        { label: 'Total marks', value: '300' },
        { label: 'Passing criteria', value: '50% aggregate (150/300)' },
    ],
    eligibility: [
        { label: 'Qualifying degree', value: 'Primary Medical Qualification (MBBS or equivalent) from a foreign institution listed in WHO World Directory of Medical Schools' },
        { label: 'Citizenship', value: 'Indian citizen or Overseas Citizen of India (OCI)' },
        { label: 'Document requirements', value: 'Eligibility Certificate from NMC, Passport, MBBS degree certificate, Internship certificate (if completed)' },
        { label: 'No age limit', value: 'Any age, but you must appear within 10 years of completing MBBS (as per NMC rules)' },
    ],
    syllabus: [
        { subject: 'Pre-clinical: Anatomy, Physiology, Biochemistry', weight: '~20%', topics: 'As per GMER 2019' },
        { subject: 'Para-clinical: Pathology, Microbiology, Pharmacology, Forensic Medicine, PSM', weight: '~30%', topics: 'Indian-context epidemiology and pharmacology are high-yield' },
        { subject: 'Medicine & Allied', weight: '~25%', topics: 'Tropical diseases, Tuberculosis, Vector-borne diseases (India-prevalent)' },
        { subject: 'Surgery & Allied', weight: '~15%', topics: 'Common Indian surgical conditions' },
        { subject: 'OBG, Paediatrics, Ophthalmology, ENT', weight: '~10%', topics: 'High-yield obstetrics, neonatal care, common infections' },
    ],
    books: [
        { name: 'Harrison + Park + Ghai + Bailey + Robbins', author: 'Standard authors', why: 'Use Indian-context textbooks, not foreign references. Indian epidemiology and pharmacology are heavily tested.' },
        { name: 'Self Assessment & Review of FMGE', author: 'Arora', why: 'MCQ book tailored for FMGE pattern.' },
        { name: 'Mudit Khanna MCQ book for FMGE', author: 'Mudit Khanna', why: 'Subject-wise FMGE MCQs with explanations.' },
        { name: 'Review of AIIMS / PGI / JIPMER', author: 'Various', why: 'Useful for image-based and clinical reasoning questions.' },
    ],
    faqs: [
        { q: 'What is FMGE?', a: 'FMGE (Foreign Medical Graduate Examination) is the screening test conducted by NBEMS for Indian citizens with primary medical qualifications from foreign institutions, required to practise medicine in India or to appear for NEET PG.' },
        { q: 'How many questions in FMGE 2026?', a: '300 MCQs across pre-clinical, para-clinical, and clinical subjects. 5 hours total. No negative marking.' },
        { q: 'What is the FMGE pass mark?', a: '50% aggregate (150 out of 300). There is no negative marking.' },
        { q: 'Who conducts FMGE?', a: 'The National Board of Examinations in Medical Sciences (NBEMS) conducts FMGE twice a year — June and December sessions.' },
        { q: 'Can FMGE preparation be done in 3 months?', a: 'Yes, with disciplined study: solve 4,000+ MCQs, take one full mock every Sunday, focus on Indian-context epidemiology and pharmacology, and use AI tutor for weak subjects.' },
        { q: 'Does CrackCMS follow FMGE pattern?', a: 'Yes. Our mock tests use 300 MCQs in the two-part format (Part A + Part B), 150 minutes each, with no negative marking.' },
    ],
    accentFrom: 'from-amber-600',
    accentTo: 'to-orange-700',
    emoji: '🌍',
    pyqCount: '8,000+',
};

export const metadata = buildExamMetadata(content);

export default function FMGEPage() {
    return ExamLandingLayout(content);
}
