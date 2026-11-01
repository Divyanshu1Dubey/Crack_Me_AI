import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import Breadcrumbs from '@/components/Breadcrumbs';
import { questionBankHref } from '@/lib/seo';
import { FMGE_PATTERN } from '@/lib/examPatterns';

const content: ExamLandingContent = {
    slug: 'fmge',
    name: 'FMGE',
    fullName: 'Foreign Medical Graduate Examination',
    title: 'FMGE Preparation 2026 — MCI Screening Test for Foreign MBBS | CrackCMS',
    description: 'Prepare for FMGE 2026 (Screening Test for foreign MBBS graduates) with an AI tutor, mock tests and practice questions from our NEET PG bank, which covers the same MBBS subjects.',
    tagline: 'Prepare for FMGE with an AI tutor, timed mock tests and practice from our NEET PG question bank (same 19 MBBS subjects).',
    heroBullets: [
        'Practise all 19 MBBS subjects in our NEET PG bank (a dedicated FMGE bank is being added)',
        'AI tutor trained on Indian medical textbooks',
        'Timed mock tests in a computer-based exam interface',
        'Personalised analytics to identify weak topics',
    ],
    stats: [
        { number: String(FMGE_PATTERN.totalQuestions), label: `MCQs (${FMGE_PATTERN.parts} parts)` },
        { number: `${FMGE_PATTERN.passMarks}/${FMGE_PATTERN.totalQuestions}`, label: 'Pass mark' },
        { number: 'None', label: 'Negative marking' },
        { number: 'NBEMS', label: 'Conducting body' },
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
        { q: 'Does CrackCMS have an FMGE question bank?', a: 'A dedicated FMGE bank is not live yet. Until it is, practise with our NEET PG bank, which covers the same MBBS subjects, and use the AI tutor for weak topics.' },
    ],
    accentFrom: 'from-amber-600',
    accentTo: 'to-orange-700',
    emoji: '🌍',
    pyqCount: '4,000+ NEET PG',
    pyqHref: questionBankHref('neet-pg'),
};

export const metadata = buildExamMetadata(content);

export default function FMGEPage() {
    return (
        <>
            <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                <Breadcrumbs items={[{ name: 'FMGE', path: '/fmge' }]} />
            </div>
            <ExamLandingLayout content={content}>
                <div className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-6">FMGE Comparisons & Resources</h2>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <Link href="/fmge/vs-next" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold group-hover:underline">FMGE vs NEXT <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">Compare FMGE (MCI Screening) with NExT for foreign MBBS graduates.</p>
                        </Link>
                        <Link href="/guides/fmge-complete-guide" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold group-hover:underline">FMGE Complete Guide <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">Strategy, books, syllabus, and 6-month study plan for FMGE 2026.</p>
                        </Link>
                    </div>
                </div>
            </ExamLandingLayout>
        </>
    );
}
