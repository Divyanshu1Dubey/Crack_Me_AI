import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { CMS_PYQ_COUNT, CMS_PYQ_PHRASE, CMS_PYQ_YEAR_COUNT, CMS_PYQ_YEARS } from '@/lib/bankStats';
import {
    CMS_MARKS_PER_QUESTION,
    CMS_NEGATIVE_MARKING_TEXT,
    CMS_PENALTY_PER_WRONG,
    UPSC_CMS_CYCLE,
    UPSC_CMS_PATTERN,
    round2,
} from '@/lib/examPatterns';
import { FREE_DAILY_AI_TOKENS, LOWEST_PLAN_PRICE_INR } from '@/app/subscription/plans';

const [paper1, paper2] = UPSC_CMS_PATTERN.papers;
const perQ = round2(CMS_MARKS_PER_QUESTION).toFixed(2);
const penalty = round2(CMS_PENALTY_PER_WRONG).toFixed(2);

const content: ExamLandingContent = {
    slug: 'cms',
    name: 'UPSC CMS',
    fullName: 'Combined Medical Services Examination',
    title: 'UPSC CMS Preparation 2026 — AI Tutor, PYQs, Mock Tests',
    description: `Prepare for UPSC CMS with ${CMS_PYQ_COUNT} previous year questions (${CMS_PYQ_YEARS}), AI explanations, full mock test series, and an exam simulator on CrackCMS.`,
    tagline: `Crack the Combined Medical Services exam with an AI tutor, ${CMS_PYQ_COUNT} PYQs (${CMS_PYQ_YEARS}), and full UPSC CMS mock tests.`,
    heroBullets: [
        `${CMS_PYQ_COUNT} previous-year UPSC CMS questions (${CMS_PYQ_YEARS})`,
        'AI tutor that explains every answer with mnemonics & textbook references',
        `Real-exam simulator with one-third negative marking and a ${paper1.durationMinutes}-min countdown per paper`,
        'Personalised analytics — see exactly which topics are dragging your rank',
    ],
    stats: [
        { number: CMS_PYQ_COUNT, label: `UPSC CMS PYQs (${CMS_PYQ_YEARS})` },
        { number: `${CMS_PYQ_YEAR_COUNT} yrs`, label: `Years covered (${CMS_PYQ_YEARS})` },
        { number: String(UPSC_CMS_PATTERN.writtenMarks), label: `Written exam marks (${paper1.marks} + ${paper2.marks})` },
        { number: UPSC_CMS_PATTERN.modeShort, label: 'Single-day, two papers' },
    ],
    pattern: [
        { label: 'Papers', value: `${paper1.name} + ${paper2.name}` },
        { label: 'Total questions', value: `${UPSC_CMS_PATTERN.totalQuestions} (${paper1.questions} + ${paper2.questions})` },
        { label: 'Time allowed', value: '02 hours per paper (9:30–11:30 AM, 2:00–4:00 PM)' },
        { label: 'Written exam marks', value: `${UPSC_CMS_PATTERN.writtenMarks} (${paper1.marks} + ${paper2.marks})` },
        { label: 'Personality Test', value: `${UPSC_CMS_PATTERN.personalityTestMarks} marks` },
        { label: 'Grand total', value: `${UPSC_CMS_PATTERN.totalMarks} marks` },
        { label: 'Marks per question', value: `≈ ${perQ} (${paper1.marks} ÷ ${paper1.questions})` },
        { label: 'Negative marking', value: CMS_NEGATIVE_MARKING_TEXT },
        { label: 'Mode', value: UPSC_CMS_PATTERN.mode },
        {
            label: 'Subjects covered',
            value: UPSC_CMS_PATTERN.papers
                .map((p) => `${p.name}: ${p.subjects.map((s) => (s.includes ? `${s.name} (incl. ${s.includes})` : s.name)).join(', ')}`)
                .join('; '),
        },
    ],
    eligibility: [
        { label: 'Nationality', value: 'Indian citizen (or subject of Nepal/Bhutan; Tibetan refugee with intent to settle in India)' },
        { label: 'Qualifying degree', value: 'MBBS (final year appearing or passed) from an NMC-recognised institution' },
        { label: 'Age limit', value: '32 years (relaxation for reserved categories per UPSC rules)' },
        { label: 'Attempts', value: UPSC_CMS_PATTERN.attemptsRule },
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
        { q: 'How many questions are in UPSC CMS?', a: `UPSC CMS has two papers of ${paper1.questions} questions each (${UPSC_CMS_PATTERN.totalQuestions} total), held on a single day as a ${UPSC_CMS_PATTERN.mode}. Paper I covers General Medicine & Paediatrics (9:30–11:30 AM, ${paper1.marks} marks). Paper II covers Surgery, Gynaecology & Obstetrics, and Preventive & Social Medicine (2:00–4:00 PM, ${paper2.marks} marks). Total written marks = ${UPSC_CMS_PATTERN.writtenMarks}. Personality Test = ${UPSC_CMS_PATTERN.personalityTestMarks} marks. Total = ${UPSC_CMS_PATTERN.totalMarks}. A correct answer is worth about ${perQ} marks and a wrong answer costs about ${penalty} (one-third).` },
        { q: 'When was UPSC CMS 2026?', a: `The UPSC CMS 2026 written exam was scheduled for 02 August 2026 (Sunday), as a single-day Computer-Based Test. The notification was released on 11 March 2026 and advertised ${UPSC_CMS_CYCLE.vacancies.toLocaleString('en-IN')} Medical Officer posts. Results and cut-offs are published by UPSC on upsc.gov.in; the next cycle's dates appear in its notification.` },
        { q: 'What is the UPSC CMS 2026 syllabus?', a: 'The CMS syllabus covers General Medicine, Surgery, Paediatrics, OBG, Preventive & Social Medicine, ENT, Ophthalmology, Anaesthesia and Orthopaedics. See the table above for high-yield topics.' },
        { q: 'Who is eligible for UPSC CMS?', a: 'Any Indian citizen with an MBBS degree from an NMC-recognised college, aged under 32 (relaxations for SC/ST/OBC/PwD), may apply.' },
        { q: 'How many PYQs does CrackCMS have for UPSC CMS?', a: `CrackCMS hosts ${CMS_PYQ_PHRASE}, with AI-powered explanations, mnemonics, textbook references and similar-PYQ links.` },
        { q: 'Can I attempt a free UPSC CMS mock test on CrackCMS?', a: `Yes — free accounts get ${FREE_DAILY_AI_TOKENS} AI tokens a day and can take short practice tests of up to 20 questions. Full-length mock tests and the complete question bank need a premium plan (from ₹${LOWEST_PLAN_PRICE_INR}/month).` },
        { q: 'Does CrackCMS follow the latest UPSC CMS exam pattern?', a: `Yes. Our mock tests use the two-paper, ${UPSC_CMS_PATTERN.totalQuestions}-question format with one-third negative marking and a ${paper1.durationMinutes}-minute countdown per paper.` },
        { q: 'How should I prepare for UPSC CMS in 6 months?', a: 'Start with subject-wise PYQs to build a baseline, take one full mock every Sunday, spend 30 minutes daily on AI tutor for weak topics, and revise mnemonics using our spaced-repetition flashcards.' },
    ],
    accentFrom: 'from-indigo-600',
    accentTo: 'to-violet-700',
    emoji: '🏛️',
    pyqCount: CMS_PYQ_COUNT,
    // Slugs must exist in content/blog (ExamLandingLayout links /blog/<slug>).
    relatedBlogPosts: [
        {
            slug: 'upsc-cms-2026-official-notification-guide',
            title: 'UPSC CMS 2026 Notification Guide: Pattern, Eligibility, Dates',
            excerpt:
                'What the UPSC CMS 2026 notice says about the exam pattern, eligibility, vacancies and key dates.',
        },
        {
            slug: 'negative-marking-strategy-upsc-cms',
            title: 'UPSC CMS Negative Marking Strategy',
            excerpt:
                'How one-third negative marking works in UPSC CMS and when an educated guess is worth it.',
        },
        {
            slug: 'upsc-cms-2024-cutoff-marks-category-wise',
            title: 'UPSC CMS 2024 Cutoff Marks: Category-Wise',
            excerpt:
                'Category-wise UPSC CMS 2024 cutoff ranges with context from recent years.',
        },
        {
            slug: 'upsc-cms-preparation-strategy-6-month-plan',
            title: 'UPSC CMS 6-Month Preparation Strategy',
            excerpt:
                'Month-by-month UPSC CMS preparation plan with daily schedule variants and PYQ-based subject triage.',
        },
    ],
};

export const metadata = buildExamMetadata(content);

export default function CMSPage() {
    return (
        <>
            <ExamLandingLayout content={content}>
                <div className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-6">Essential UPSC CMS Resources</h2>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <Link href="/cms/cutoff" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Cutoff</p>
                            <p className="mt-1 font-semibold group-hover:underline">UPSC CMS Cutoffs <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Category-wise qualifying marks</p>
                        </Link>
                        <Link href="/cms/exam-pattern" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Pattern</p>
                            <p className="mt-1 font-semibold group-hover:underline">Exam Pattern & Syllabus <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">{UPSC_CMS_PATTERN.totalQuestions} MCQs, marking scheme, subjects</p>
                        </Link>
                        <Link href="/cms/salary" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Career</p>
                            <p className="mt-1 font-semibold group-hover:underline">Salary & Promotion <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Pay structure, NPA, career growth</p>
                        </Link>
                        <Link href="/cms/vs-neet-pg" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Compare</p>
                            <p className="mt-1 font-semibold group-hover:underline">CMS vs NEET PG <ArrowRight className="inline ml-1 h-3 w-3" /></p>
                            <p className="mt-1 text-xs text-muted-foreground">Which exam suits your goals?</p>
                        </Link>
                    </div>
                </div>
            </ExamLandingLayout>
        </>
    );
}
