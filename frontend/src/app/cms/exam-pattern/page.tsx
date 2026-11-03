import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import Breadcrumbs from '@/components/Breadcrumbs';
import { jsonLdString } from '@/lib/metadata';
import {
    CMS_MARKS_PER_QUESTION,
    CMS_PENALTY_PER_WRONG,
    UPSC_CMS_PATTERN,
    round2,
} from '@/lib/examPatterns';

const perQ = round2(CMS_MARKS_PER_QUESTION).toFixed(2);
const penalty = round2(CMS_PENALTY_PER_WRONG).toFixed(2);
const [paper1, paper2] = UPSC_CMS_PATTERN.papers;

const title = 'UPSC CMS Exam Pattern 2026 — Papers, Marks, Negative Marking, Subjects';
const description = `Complete UPSC CMS 2026 exam pattern: ${UPSC_CMS_PATTERN.papers.length} computer-based papers, ${UPSC_CMS_PATTERN.totalQuestions} MCQs, ${UPSC_CMS_PATTERN.writtenMarks} written marks + ${UPSC_CMS_PATTERN.personalityTestMarks}-mark Personality Test, one-third negative marking. Subject-wise question distribution and marking scheme explained.`;
const slug = 'cms-exam-pattern';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug, path: '/cms/exam-pattern' });

const faqs = [
    {
        q: 'What is the UPSC CMS 2026 exam pattern?',
        a: `UPSC CMS has two papers of ${paper1.questions} MCQs each (${UPSC_CMS_PATTERN.totalQuestions} in total), ${paper1.durationMinutes} minutes and ${paper1.marks} marks per paper (${UPSC_CMS_PATTERN.writtenMarks} written marks), conducted as a ${UPSC_CMS_PATTERN.mode}. Candidates who qualify then take a ${UPSC_CMS_PATTERN.personalityTestMarks}-mark Personality Test, for ${UPSC_CMS_PATTERN.totalMarks} marks in all.`,
    },
    {
        q: 'Is UPSC CMS online or offline?',
        a: `UPSC CMS Part I is a ${UPSC_CMS_PATTERN.mode}: both papers are answered on a computer at the exam centre. Check the admit card and the current notification on upsc.gov.in for the exact instructions.`,
    },
    {
        q: 'How many marks per question in UPSC CMS?',
        a: `Each paper has ${paper1.marks} marks for ${paper1.questions} questions, so a correct answer is worth about ${perQ} marks. A wrong answer costs one-third of that (about ${penalty} marks). Unattempted questions carry 0 marks.`,
    },
    {
        q: 'Is there negative marking in UPSC CMS?',
        a: `Yes — one-third of the marks assigned to a question is deducted for each wrong answer (about ${penalty} of ${perQ}). Leaving a question blank costs nothing, so attempt a question when you can rule out at least two options.`,
    },
    {
        q: 'How many total questions are there in UPSC CMS?',
        a: `UPSC CMS has ${UPSC_CMS_PATTERN.totalQuestions} MCQs in total — ${paper1.questions} in Paper I and ${paper2.questions} in Paper II. Each paper carries ${paper1.marks} marks, for ${UPSC_CMS_PATTERN.writtenMarks} written marks.`,
    },
    {
        q: 'What are the qualifying marks for UPSC CMS?',
        a: `UPSC does not fix a qualifying percentage in advance. Candidates are shortlisted for the Personality Test on their written score out of ${UPSC_CMS_PATTERN.writtenMarks}, and the cut-off varies by year and category. Recent General-category written cut-offs have been roughly 280-310 out of ${UPSC_CMS_PATTERN.writtenMarks}; verify on upsc.gov.in.`,
    },
];

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.slice(0, 3).map((f) => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
    })),
};

const cell = 'border border-border px-4 py-3';

export default function CMSExamPatternPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Exam Pattern', path: '/cms/exam-pattern' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Exam Pattern 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        UPSC CMS Part I is a <strong>{UPSC_CMS_PATTERN.mode}</strong> with two papers of {paper1.questions} MCQs
                        each, followed by a {UPSC_CMS_PATTERN.personalityTestMarks}-mark Personality Test. Here is the complete exam
                        pattern, marking scheme, subject-wise distribution, and negative marking rule for the 2026 cycle.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-4">Exam Pattern Overview</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse rounded-xl border border-border overflow-hidden">
                            <thead>
                                <tr className="bg-muted">
                                    <th className={`${cell} text-left text-sm font-bold`}>Component</th>
                                    <th className={`${cell} text-left text-sm font-bold`}>{paper1.name}</th>
                                    <th className={`${cell} text-left text-sm font-bold`}>{paper2.name}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className={cell}>Total Questions</td><td className={cell}>{paper1.questions}</td><td className={cell}>{paper2.questions}</td></tr>
                                <tr><td className={cell}>Total Marks</td><td className={cell}>{paper1.marks}</td><td className={cell}>{paper2.marks}</td></tr>
                                <tr><td className={cell}>Duration</td><td className={cell}>{paper1.durationMinutes} minutes</td><td className={cell}>{paper2.durationMinutes} minutes</td></tr>
                                <tr><td className={cell}>Marks per Question</td><td className={cell}>≈ {perQ}</td><td className={cell}>≈ {perQ}</td></tr>
                                <tr><td className={cell}>Negative Marking</td><td className={cell}>⅓ of the question&apos;s marks (≈ −{penalty})</td><td className={cell}>⅓ of the question&apos;s marks (≈ −{penalty})</td></tr>
                                <tr><td className={cell}>Mode</td><td className={cell}>{UPSC_CMS_PATTERN.modeShort}</td><td className={cell}>{UPSC_CMS_PATTERN.modeShort}</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">
                        Written total: {UPSC_CMS_PATTERN.writtenMarks} marks. Personality Test: {UPSC_CMS_PATTERN.personalityTestMarks} marks.
                        Final merit: {UPSC_CMS_PATTERN.totalMarks} marks.
                    </p>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Subject-wise Question Distribution</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse rounded-xl border border-border overflow-hidden">
                            <thead>
                                <tr className="bg-muted">
                                    <th className={`${cell} text-left text-sm font-bold`}>Paper</th>
                                    <th className={`${cell} text-left text-sm font-bold`}>Subject</th>
                                    <th className={`${cell} text-left text-sm font-bold`}>Questions</th>
                                    <th className={`${cell} text-left text-sm font-bold`}>Marks (approx.)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {UPSC_CMS_PATTERN.papers.map((paper) =>
                                    paper.subjects.map((subject, i) => (
                                        <tr key={`${paper.name}-${subject.name}`}>
                                            {i === 0 && (
                                                <td className={cell} rowSpan={paper.subjects.length}>{paper.name}</td>
                                            )}
                                            <td className={cell}>
                                                {subject.name}
                                                {subject.includes && (
                                                    <span className="block text-xs text-muted-foreground">including {subject.includes}</span>
                                                )}
                                            </td>
                                            <td className={cell}>{subject.questions}</td>
                                            <td className={cell}>{round2(subject.questions * CMS_MARKS_PER_QUESTION).toFixed(1)}</td>
                                        </tr>
                                    )),
                                )}
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">
                        * Question split as given in the UPSC CMS notice. Always re-check the current notification on upsc.gov.in.
                    </p>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Marking Scheme &amp; Negative Marking</h2>
                    <div className="grid gap-4 sm:grid-cols-3">
                        <div className="rounded-xl border border-border bg-card p-5">
                            <p className="text-2xl font-black text-green-600">+{perQ}</p>
                            <p className="text-sm text-muted-foreground mt-1">Marks for each correct answer ({paper1.marks} ÷ {paper1.questions})</p>
                        </div>
                        <div className="rounded-xl border border-border bg-card p-5">
                            <p className="text-2xl font-black text-red-600">−{penalty}</p>
                            <p className="text-sm text-muted-foreground mt-1">Deducted per wrong answer (one-third of the question&apos;s marks)</p>
                        </div>
                        <div className="rounded-xl border border-border bg-card p-5">
                            <p className="text-2xl font-black text-muted-foreground">0</p>
                            <p className="text-sm text-muted-foreground mt-1">Marks for unattempted questions</p>
                        </div>
                    </div>
                    <p className="mt-4 text-sm text-muted-foreground">
                        With one-third negative marking, a blind guess among four options has an expected value of zero.
                        <strong> Rule of thumb:</strong> attempt when you have eliminated at least two options.
                    </p>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {faqs.map((faq) => (
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
