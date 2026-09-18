import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

const content: ExamLandingContent = {
    slug: 'medical-officer',
    name: 'Medical Officer',
    fullName: 'Medical Officer Recruitment Exams',
    title: 'Medical Officer Exam Preparation — State & Central Govt MO Jobs | CrackCMS',
    description: 'Prepare for Medical Officer recruitment exams — state PSC, NHM, ESIC, Railways & Defence. Practice PYQs, mock tests and AI explanations on CrackCMS.',
    tagline: 'Crack Medical Officer recruitment exams — state PSCs, NHM, ESIC, Railways, Defence. AI-powered MCQs and mock tests.',
    heroBullets: [
        '6,000+ Medical Officer PYQs across all state and central recruitments',
        'State-specific exam coverage — UP, MP, Rajasthan, Bihar, TN, Maharashtra',
        'AI tutor explains every answer with public-health context',
        'Mock tests with negative marking and 60-min countdowns',
    ],
    stats: [
        { number: '6,000+', label: 'MO PYQs' },
        { number: '4.8/5', label: 'User rating' },
        { number: '47k+', label: 'Active aspirants' },
        { number: '28 states', label: 'Coverage' },
    ],
    pattern: [
        { label: 'Common pattern', value: '100-200 MCQs, 60-120 min, -0.25 or -0.33 negative marking' },
        { label: 'Subjects', value: 'General Medicine, Surgery, Paediatrics, OBG, PSM, G&O, Anatomy, Physiology' },
        { label: 'State variations', value: 'Some states add GK, reasoning, and English (UPPSC, MPPSC pattern)' },
        { label: 'Recruiters', value: 'State PSCs (UPPSC, MPPSC, RPSC, BPSC), NHM, ESIC, DFSS, RRB, AIIMS, PGI' },
        { label: 'Salary', value: 'Pay Level-10 (₹56,100-1,77,500) + NPA + rural allowance' },
    ],
    eligibility: [
        { label: 'Qualifying degree', value: 'MBBS from an NMC-recognised college' },
        { label: 'Registration', value: 'Permanent registration with NMC / State Medical Council' },
        { label: 'Age limit', value: '21-40 years (relaxation for reserved categories)' },
        { label: 'Citizenship', value: 'Indian citizen (some state posts require domicile)' },
    ],
    syllabus: [
        { subject: 'General Medicine', weight: '~25%', topics: 'Cardiology, Respiratory, GI, Infectious diseases, Endocrinology' },
        { subject: 'General Surgery', weight: '~15%', topics: 'Common surgical conditions, Trauma, Oncology' },
        { subject: 'Paediatrics', weight: '~10%', topics: 'Neonatology, Immunisation, Common infections' },
        { subject: 'OBG', weight: '~10%', topics: 'Antenatal care, High-risk pregnancy' },
        { subject: 'PSM / Community Medicine', weight: '~20%', topics: 'Epidemiology, National Health Programmes, Biostatistics' },
        { subject: 'Anatomy, Physiology, Biochemistry', weight: '~10%', topics: 'Basics for clinical reasoning' },
        { subject: 'GK + Reasoning (state PSCs)', weight: '~10%', topics: 'Current affairs, History, Polity (only for some states)' },
    ],
    books: [
        { name: 'Harrison + Park + Ghai', author: 'Standard authors', why: 'Core MBBS textbooks — most MO questions are derivations from these.' },
        { name: 'Review of PSM (Vivek Jain)', author: 'Vivek Jain', why: 'Most-tested PSM book for MO exams.' },
        { name: 'State-specific MCQ books', author: 'Various', why: 'UPPSC, MPPSC, RPSC publish their own MCQ compilations.' },
        { name: 'Lucent\'s GK (for state PSCs)', author: 'Lucent', why: 'Covers General Knowledge portion of state PSC exams.' },
    ],
    faqs: [
        { q: 'What is a Medical Officer exam?', a: 'A Medical Officer exam is conducted by state Public Service Commissions (UPPSC, MPPSC, etc.), central bodies (ESIC, NHM, DFSS), and Railways (RRB) to recruit MBBS doctors for government service.' },
        { q: 'What is the salary of a Medical Officer?', a: 'Central government Medical Officers are paid as per Pay Level-10 (₹56,100 - ₹1,77,500) plus Non-Practising Allowance (NPA), rural allowance, and HRA. State salaries vary.' },
        { q: 'Which is the easiest MO exam?', a: 'State NHM and ESI Corporation recruitments typically have shorter syllabi and predictable MCQ patterns. UPSC CMS is the most prestigious central MO exam.' },
        { q: 'How to crack MO exam in 3 months?', a: 'Solve 3,000+ PYQs, focus on PSM and Medicine (highest weightage), take 6 full mocks, and use AI tutor for reasoning on tricky clinical MCQs.' },
        { q: 'Does CrackCMS cover my state?', a: 'Yes — we have state-specific filters for UP, MP, Rajasthan, Bihar, Tamil Nadu, Maharashtra, Karnataka, West Bengal and more.' },
    ],
    accentFrom: 'from-sky-600',
    accentTo: 'to-blue-700',
    emoji: '🩺',
    pyqCount: '6,000+',
};

export const metadata = buildExamMetadata(content);

export default function MedicalOfficerPage() {
    return (
        <>
            <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                <Breadcrumbs items={[{ name: 'Medical Officer', path: '/medical-officer' }]} />
            </div>
            <ExamLandingLayout content={content}>
                <div className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-6">Career Paths After Medical Officer Exam</h2>
                    <div className="grid gap-4 sm:grid-cols-3">
                        <Link href="/cms/salary" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Salary</p>
                            <p className="mt-1 font-semibold group-hover:underline">UPSC CMS Salary & Career <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Pay structure, NPA, promotion hierarchy, in-hand pay</p>
                        </Link>
                        <Link href="/cms" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">UPSC CMS</p>
                            <p className="mt-1 font-semibold group-hover:underline">Prepare for UPSC CMS <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Central government MO posts through UPSC</p>
                        </Link>
                        <Link href="/government-doctor-jobs" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Jobs</p>
                            <p className="mt-1 font-semibold group-hover:underline">Government Doctor Jobs <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Central & state MO recruitment opportunities</p>
                        </Link>
                    </div>
                </div>
            </ExamLandingLayout>
        </>
    );
}
