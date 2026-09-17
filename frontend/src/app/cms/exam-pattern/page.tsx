import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import Script from 'next/script';

const title = 'UPSC CMS Exam Pattern 2026 — Papers, Marks, Negative Marking, Subjects';
const description = 'Complete UPSC CMS 2026 exam pattern: 2 papers, 240 MCQs, 960 marks, -0.33 negative marking, pen-and-paper mode. Subject-wise question distribution and marking scheme explained.';
const slug = 'cms-exam-pattern';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        {
            '@type': 'Question',
            name: 'What is the UPSC CMS 2026 exam pattern?',
            acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS 2026 has 2 papers of 120 MCQs each (240 total), 120 minutes per paper, 960 total marks, -0.33 negative marking per wrong answer, conducted in offline pen-and-paper mode.' },
        },
        {
            '@type': 'Question',
            name: 'Is UPSC CMS online or offline?',
            acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS is conducted in offline pen-and-paper (OMR) mode. Candidates mark answers on an OMR sheet with a black ballpoint pen. No computer-based test interface is used.' },
        },
        {
            '@type': 'Question',
            name: 'How many marks per question in UPSC CMS?',
            acceptedAnswer: { '@type': 'Answer', text: 'Each correct answer carries 4 marks in UPSC CMS. Each wrong answer attracts a penalty of -0.33 marks. Unattempted questions carry 0 marks.' },
        },
    ],
};

export default function CMSExamPatternPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Exam Pattern', path: '/cms/exam-pattern' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Exam Pattern 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        UPSC CMS is conducted in <strong>offline pen-and-paper mode</strong> with two papers of 120 MCQs each.
                        Here is the complete exam pattern, marking scheme, subject-wise distribution, and negative marking rules
                        for the 2026 cycle.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-4">Exam Pattern Overview</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse rounded-xl border border-border overflow-hidden">
                            <thead>
                                <tr className="bg-muted">
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Component</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Paper I</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Paper II</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className="border border-border px-4 py-3">Total Questions</td><td className="border border-border px-4 py-3">120</td><td className="border border-border px-4 py-3">120</td></tr>
                                <tr><td className="border border-border px-4 py-3">Total Marks</td><td className="border border-border px-4 py-3">480</td><td className="border border-border px-4 py-3">480</td></tr>
                                <tr><td className="border border-border px-4 py-3">Duration</td><td className="border border-border px-4 py-3">120 minutes</td><td className="border border-border px-4 py-3">120 minutes</td></tr>
                                <tr><td className="border border-border px-4 py-3">Marks per Question</td><td className="border border-border px-4 py-3">4</td><td className="border border-border px-4 py-3">4</td></tr>
                                <tr><td className="border border-border px-4 py-3">Negative Marking</td><td className="border border-border px-4 py-3">-0.33</td><td className="border border-border px-4 py-3">-0.33</td></tr>
                                <tr><td className="border border-border px-4 py-3">Mode</td><td className="border border-border px-4 py-3">Offline (OMR)</td><td className="border border-border px-4 py-3">Offline (OMR)</td></tr>
                            </tbody>
                        </table>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Subject-wise Question Distribution</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse rounded-xl border border-border overflow-hidden">
                            <thead>
                                <tr className="bg-muted">
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Paper</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Subject</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Questions</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Marks</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className="border border-border px-4 py-3" rowSpan={5}>Paper I</td><td className="border border-border px-4 py-3">General Medicine</td><td className="border border-border px-4 py-3">96</td><td className="border border-border px-4 py-3">384</td></tr>
                                <tr><td className="border border-border px-4 py-3">Paediatrics</td><td className="border border-border px-4 py-3">24</td><td className="border border-border px-4 py-3">96</td></tr>
                                <tr><td className="border border-border px-4 py-3">Dermatology</td><td className="border border-border px-4 py-3">~12</td><td className="border border-border px-4 py-3">~48</td></tr>
                                <tr><td className="border border-border px-4 py-3">Psychiatry</td><td className="border border-border px-4 py-3">~12</td><td className="border border-border px-4 py-3">~48</td></tr>
                                <tr><td className="border border-border px-4 py-3">Radiology</td><td className="border border-border px-4 py-3">~12</td><td className="border border-border px-4 py-3">~48</td></tr>
                                <tr><td className="border border-border px-4 py-3" rowSpan={5}>Paper II</td><td className="border border-border px-4 py-3">General Surgery</td><td className="border border-border px-4 py-3">40</td><td className="border border-border px-4 py-3">160</td></tr>
                                <tr><td className="border border-border px-4 py-3">OBG (Obstetrics &amp; Gynaecology)</td><td className="border border-border px-4 py-3">40</td><td className="border border-border px-4 py-3">160</td></tr>
                                <tr><td className="border border-border px-4 py-3">PSM (Preventive &amp; Social Medicine)</td><td className="border border-border px-4 py-3">40</td><td className="border border-border px-4 py-3">160</td></tr>
                                <tr><td className="border border-border px-4 py-3">ENT</td><td className="border border-border px-4 py-3">~15</td><td className="border border-border px-4 py-3">~60</td></tr>
                                <tr><td className="border border-border px-4 py-3">Ophthalmology + Orthopaedics + Anaesthesia</td><td className="border border-border px-4 py-3">~25</td><td className="border border-border px-4 py-3">~100</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">* Subject-wise distribution is based on past papers. UPSC may vary the exact count slightly each year.</p>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Marking Scheme &amp; Negative Marking</h2>
                    <div className="grid gap-4 sm:grid-cols-3">
                        <div className="rounded-xl border border-border bg-card p-5">
                            <p className="text-2xl font-black text-green-600">+4</p>
                            <p className="text-sm text-muted-foreground mt-1">Marks for each correct answer</p>
                        </div>
                        <div className="rounded-xl border border-border bg-card p-5">
                            <p className="text-2xl font-black text-red-600">-0.33</p>
                            <p className="text-sm text-muted-foreground mt-1">Negative marking per wrong answer</p>
                        </div>
                        <div className="rounded-xl border border-border bg-card p-5">
                            <p className="text-2xl font-black text-muted-foreground">0</p>
                            <p className="text-sm text-muted-foreground mt-1">Marks for unattempted questions</p>
                        </div>
                    </div>
                    <p className="mt-4 text-sm text-muted-foreground">
                        With -0.33 negative marking, the expected score for a random guess is slightly negative.
                        <strong> Rule of thumb:</strong> attempt only if you have eliminated at least 2 options.
                    </p>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'Is UPSC CMS online or offline?', a: 'UPSC CMS is conducted in offline pen-and-paper (OMR) mode. Candidates mark answers on an OMR sheet with a black ballpoint pen. The exam is not computer-based.' },
                            { q: 'How many marks per question in UPSC CMS?', a: 'Each correct answer carries 4 marks. Each wrong answer attracts a penalty of -0.33 marks. Unattempted questions carry 0 marks. There is no negative marking for leaving a question blank.' },
                            { q: 'Is there negative marking in UPSC CMS?', a: 'Yes, UPSC CMS has negative marking of -0.33 for every wrong answer. This is relatively mild compared to INI-CET (-1) or NEET PG (no negative marking). The strategy is to attempt questions only when reasonably confident.' },
                            { q: 'How many total questions are there in UPSC CMS?', a: 'UPSC CMS has 240 MCQs total — 120 in Paper I and 120 in Paper II. Both papers carry 480 marks each, for a total of 960 marks.' },
                            { q: 'What is the qualifying marks for UPSC CMS?', a: 'UPSC CMS does not have a fixed qualifying percentage. Candidates are ranked based on total marks out of 960. The cutoff varies yearly by category. General category cutoffs have ranged 340-400 out of 960 in recent years.' },
                        ].map((faq) => (
                            <div key={faq.q} className="rounded-xl border border-border bg-card p-5">
                                <h3 className="font-bold text-sm">{faq.q}</h3>
                                <p className="mt-2 text-sm text-muted-foreground">{faq.a}</p>
                            </div>
                        ))}
                    </div>
                </section>
            </div>
        </>
    );
}
