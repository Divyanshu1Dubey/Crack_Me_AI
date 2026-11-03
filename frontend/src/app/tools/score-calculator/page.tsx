import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import Breadcrumbs from '@/components/Breadcrumbs';
import { jsonLdString } from '@/lib/metadata';
import {
    CMS_MARKING_LABEL,
    CMS_MARKS_PER_QUESTION,
    CMS_PENALTY_PER_WRONG,
    UPSC_CMS_PATTERN,
    round2,
} from '@/lib/examPatterns';
import ScoreCalculator from './ScoreCalculator';

const perQ = round2(CMS_MARKS_PER_QUESTION).toFixed(2);
const penalty = round2(CMS_PENALTY_PER_WRONG).toFixed(2);
const paper = UPSC_CMS_PATTERN.papers[0];

const title = `UPSC CMS Score Calculator 2026 — ${CMS_MARKING_LABEL} Marking Scheme`;
const description = `Calculate your UPSC CMS 2026 score online using the official marking scheme (${perQ} marks per correct answer, one-third negative marking of ${penalty} per wrong answer). Get an instant estimate of your raw score, percentage, and performance level.`;
const slug = 'score-calculator';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug, path: `/tools/${slug}` });

const faqs = [
    {
        q: 'What is the marking scheme for UPSC CMS 2026?',
        a: `Each UPSC CMS paper carries ${paper.marks} marks for ${paper.questions} questions, so a correct answer earns about ${perQ} marks. A wrong answer costs one-third of that (about ${penalty} marks). Unattempted questions carry zero marks.`,
    },
    {
        q: 'How is the UPSC CMS written score calculated?',
        a: `Score = (Correct answers × ${perQ}) − (Incorrect answers × ${penalty}). Unattempted questions do not affect the score. The maximum is ${paper.marks} per paper and ${UPSC_CMS_PATTERN.writtenMarks} for both papers; the ${UPSC_CMS_PATTERN.personalityTestMarks}-mark Personality Test is added for the final merit (${UPSC_CMS_PATTERN.totalMarks} in all).`,
    },
    {
        q: 'Is there negative marking in UPSC CMS?',
        a: `Yes. One-third of the marks assigned to a question (about ${penalty} marks) is deducted for each wrong answer. There is no penalty for leaving a question blank, so it is advisable to attempt only those questions you are reasonably confident about.`,
    },
    {
        q: 'What is a good score in UPSC CMS for final selection?',
        a: `Cut-offs vary each year with paper difficulty and vacancies. In recent years the General-category written cutoff has been roughly 280-310 out of ${UPSC_CMS_PATTERN.writtenMarks} (see our cutoff pages and verify on upsc.gov.in).`,
    },
];

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((f) => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
    })),
};

export default function ScoreCalculatorPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Score Calculator', path: '/tools/score-calculator' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        Score Calculator 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Use this free UPSC CMS Score Calculator to estimate your score from the official marking scheme
                        ({CMS_MARKING_LABEL} per question). Enter your correct, incorrect, and unattempted answers to
                        instantly see your raw score, percentage, accuracy, and a performance verdict.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <ScoreCalculator />

                    <h2 className="text-2xl font-bold mt-12 mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <p className="mt-2">
                                Enter the total number of questions, your correct answers, incorrect answers, and unattempted questions.
                                Click <strong className="text-foreground">Calculate Score Breakdown</strong> to instantly see your raw score,
                                percentage, accuracy, and a performance label. Use {paper.questions} questions for one paper or{' '}
                                {UPSC_CMS_PATTERN.totalQuestions} for both.
                            </p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p className="mt-2">
                                UPSC CMS deducts one-third of a question&apos;s marks for every wrong answer. Three wrong guesses
                                cancel one correct answer. Use this calculator to see how much guessing changes your result and to
                                estimate your standing against recent cut-offs.
                            </p>
                        </div>
                    </div>

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
