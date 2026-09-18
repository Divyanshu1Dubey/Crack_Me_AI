import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

const title = 'INI-CET Complete Guide 2026 — AIIMS, PGI, JIPMER, NIMHANS Strategy';
const description = 'Complete INI-CET 2026 preparation guide for AIIMS, PIMER, JIPMER, NIMHANS, SCTIMST. Syllabus, exam pattern, books, cutoff, preparation strategy, and 4-month study plan for INI-CET January and July sessions.';
const slug = 'ini-cet-complete-guide';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'What is INI-CET?', a: 'INI-CET (Institute of National Importance - Combined Entrance Test) is the common entrance exam for PG medical courses at AIIMS, PGIMER Chandigarh, JIPMER Puducherry, NIMHANS Bangalore, and SCTIMST Trivandrum. It is conducted twice a year by AIIMS New Delhi.' },
    { q: 'How many times is INI-CET held per year?', a: 'Twice a year — January session and July session. The January 2026 session was held on 24 January 2026. The July 2026 session is expected in mid-July 2026.' },
    { q: 'How many questions in INI-CET?', a: '200 MCQs, 180 minutes, 1 mark each, -1/3 negative marking, total 200 marks.' },
    { q: 'Is INI-CET harder than NEET PG?', a: 'INI-CET questions test conceptual depth and image-based reasoning more than NEET PG. Cut-offs are typically higher relative to the candidate pool. However, both exams share the same core syllabus.' },
    { q: 'Can I appear for INI-CET while doing internship?', a: 'Yes — if your internship completes by the cutoff date mentioned in the January/July session information bulletin. Provisional registration is allowed.' },
    { q: 'What is the cutoff for INI-CET?', a: 'INI-CET cutoffs vary by institute and category. AIIMS General category cutoffs typically range 60-75 out of 200. Check individual institute websites for the latest cutoffs.' },
];

export default function INICETGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="INI-CET Complete Guide 2026"
            lede="Crack INI-CET for AIIMS, PGIMER, JIPMER, and NIMHANS. Exam pattern, subject-wise strategy, cutoffs, and 4-month preparation plan."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="10 min"
            faqs={faqs}
        >
            <h2>INI-CET exam pattern at a glance</h2>
            <ul>
                <li>Mode: Computer-Based Test (CBT) — online</li>
                <li>Total questions: 200 MCQs</li>
                <li>Duration: 180 minutes (3 hours)</li>
                <li>Marks per question: 1 mark</li>
                <li>Negative marking: -1/3 per wrong answer</li>
                <li>Total marks: 200</li>
                <li>Frequency: Twice a year (January and July sessions)</li>
                <li>No subject-wise section timing — all 200 questions in one block</li>
            </ul>

            <h2>INI-CET syllabus (19 subjects)</h2>
            <p>INI-CET covers the same 19 subjects as NEET PG, but with greater emphasis on conceptual and image-based questions:</p>
            <ul>
                <li><strong>Pre-clinical (15%):</strong> Anatomy, Physiology, Biochemistry — high-yield topics only</li>
                <li><strong>Para-clinical (25%):</strong> Pathology, Microbiology, Pharmacology, Forensic Medicine, PSM</li>
                <li><strong>Medicine &amp; Allied (25%):</strong> Cardiology, Neurology, Endocrinology, Respiratory, GI, Infectious diseases</li>
                <li><strong>Surgery &amp; Allied (20%):</strong> GI surgery, Urology, Orthopaedics, Anaesthesia</li>
                <li><strong>OBG &amp; Paediatrics (15%):</strong> Antenatal care, Gynae oncology, Neonatology, Common childhood diseases</li>
            </ul>

            <h2>Best books for INI-CET preparation</h2>
            <ol>
                <li><strong>Harrison + AIIMS-PGI Surgery guide</strong> — best combo for INI-CET Medicine + Surgery.</li>
                <li><strong>AIIMS PG solved papers</strong> — last 10 years of AIIMS papers with explanations.</li>
                <li><strong>Self Assessment &amp; Review of NEET/AIIMS Pattern (Arora)</strong> — single-volume MCQ book for revision.</li>
                <li><strong>PGI Chandigarh solved papers</strong> — pattern-setter for INI-CET.</li>
                <li><strong>CrackCMS INI-CET QBank</strong> — 12,000+ PYQs with AI explanations, image-based filters, and CBT mocks.</li>
            </ol>

            <h2>INI-CET preparation strategy (4-month plan)</h2>
            <h3>Month 1: Foundation</h3>
            <ul>
                <li>Revise standard textbooks (Harrison, Bailey, Ghai, Park)</li>
                <li>Solve 100 MCQs/day from CrackCMS INI-CET QBank</li>
                <li>Focus on image-based subjects: Radiology, Pathology, Dermatology</li>
            </ul>
            <h3>Month 2: Deep Dive</h3>
            <ul>
                <li>Solve 150 MCQs/day from previous AIIMS papers</li>
                <li>Take one full mock every Sunday</li>
                <li>Analyse every mock — identify weak areas</li>
                <li>Start PSM revision (high weightage, often neglected)</li>
            </ul>
            <h3>Month 3: Image-Based Sprint</h3>
            <ul>
                <li>Dedicated image-based MCQ practice (radiology, histopath, derm)</li>
                <li>Solve 200 MCQs/day from random topics</li>
                <li>Revise mnemonics and high-yield notes</li>
                <li>Take 2 mocks per week under timed conditions</li>
            </ul>
            <h3>Month 4: Final Sprint</h3>
            <ul>
                <li>Full mocks every alternate day</li>
                <li>Revise weak areas only — no new topics</li>
                <li>Review all previous mocks and mistakes</li>
                <li>Focus on time management (200 Qs in 180 min = 54 sec/Q)</li>
            </ul>

            <h2>INI-CET vs NEET PG — Which is harder?</h2>
            <p>
                <strong>INI-CET</strong> is generally considered slightly tougher than NEET PG due to deeper clinical reasoning,
                image-based questions, and -1/3 negative marking. NEET PG has a slightly higher negative marking penalty
                (-1 vs -1/3). Most serious candidates attempt both.
                See our detailed <a href="/neet-pg/vs-ini-cet" className="text-primary underline">NEET PG vs INI-CET</a> comparison.
            </p>

            <h2>Essential INI-CET Resources</h2>
            <div className="grid gap-4 sm:grid-cols-2">
                <Link href="/ini-cet" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                    <p className="text-sm font-bold group-hover:underline">INI-CET Preparation <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                    <p className="mt-1 text-sm text-muted-foreground">12,000+ PYQs, AI tutor, CBT mocks, rank predictor for AIIMS, PGI, JIPMER.</p>
                </Link>
                <Link href="/neet-pg/vs-ini-cet" className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                    <p className="text-sm font-bold group-hover:underline">NEET PG vs INI-CET <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                    <p className="mt-1 text-sm text-muted-foreground">Side-by-side comparison of pattern, difficulty, negative marking, and career outcomes.</p>
                </Link>
            </div>

            <h2>Why CrackCMS for INI-CET?</h2>
            <ul>
                <li>12,000+ INI-CET MCQs with image-based filters for radiology, pathology, dermatology</li>
                <li>AI tutor trained on AIIMS-pattern clinical reasoning</li>
                <li>CBT mocks that simulate the exact AIIMS interface</li>
                <li>All-India rank prediction using historical AIIMS cutoffs</li>
                <li>Image-based MCQ drill with 1,000+ curated slides and X-rays</li>
            </ul>
        </GuideLayout>
    );
}
