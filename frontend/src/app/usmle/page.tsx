import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import Breadcrumbs from '@/components/Breadcrumbs';

const content: ExamLandingContent = {
    slug: 'usmle',
    name: 'USMLE',
    fullName: 'United States Medical Licensing Examination',
    title: 'USMLE Step 1 Preparation — Guide, AI Tutor, Study Plan',
    description: 'USMLE Step 1 preparation for Indian medical graduates: exam pattern, eligibility, resources and an AI tutor. A CrackCMS USMLE question bank is in development — join the waitlist.',
    tagline: 'Plan USMLE Step 1 with our guide and AI tutor. A USMLE question bank is in development — join the waitlist for early access.',
    heroBullets: [
        'USMLE Step 1 / Step 2 CK question bank in development — join the waitlist',
        'AI tutor for concept gaps across basic and clinical sciences',
        'Spaced-repetition (SM-2) flashcards for high-yield facts',
        'Free USMLE Step 1 guide for Indian MBBS graduates',
    ],
    stats: [
        { number: 'Coming soon', label: 'USMLE question bank' },
        { number: '280', label: 'Step 1 MCQs (7 blocks)' },
        { number: 'Pass/Fail', label: 'Step 1 scoring' },
        { number: '8 h', label: 'Step 1 test day' },
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
        { q: 'Does CrackCMS replace UWorld?', a: 'No — UWorld is the standard USMLE question bank. CrackCMS can complement it with an AI tutor for concept gaps; our own USMLE question bank is still in development.' },
    ],
    accentFrom: 'from-purple-600',
    accentTo: 'to-indigo-700',
    emoji: '🇺🇸',
    pyqCount: 'USMLE',
    pyqHref: null,
    relatedBlogPosts: [
        { slug: 'best-pg-medical-entrance-books', title: '', excerpt: '' },
        { slug: 'memorization-techniques-medical-aspirants', title: '', excerpt: '' },
        { slug: 'stress-management-medical-exams', title: '', excerpt: '' },
    ],
};

export const metadata = buildExamMetadata(content);

export default function USMLEPage() {
    return (
        <>
            <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                <Breadcrumbs items={[{ name: 'USMLE', path: '/usmle' }]} />
            </div>
            <ExamLandingLayout content={content}>
                <div className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-6">For Indian MBBS Graduates: USMLE vs Alternatives</h2>
                    <div className="grid gap-4 sm:grid-cols-3">
                        <Link href="/neet-pg/vs-usmle" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Compare</p>
                            <p className="mt-1 font-semibold group-hover:underline">NEET PG vs USMLE <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Which route fits your budget and goals?</p>
                        </Link>
                        <Link href="/neet-pg" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Alternative</p>
                            <p className="mt-1 font-semibold group-hover:underline">NEET PG Preparation <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">MD/MS in India — 2,300+ PYQs + AI tutor</p>
                        </Link>
                        <Link href="/guides/usmle-step-1-guide" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Guide</p>
                            <p className="mt-1 font-semibold group-hover:underline">USMLE Step 1 Guide for Indians <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Costs, timeline, ECFMG, and prep strategy</p>
                        </Link>
                    </div>
                </div>
            </ExamLandingLayout>
        </>
    );
}
