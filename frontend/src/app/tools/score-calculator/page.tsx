import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import ScoreCalculator from './ScoreCalculator';

const title = 'UPSC CMS Score Calculator 2026 — +3/-1 Marking Scheme';
const description = 'Calculate your UPSC CMS 2026 score online using the official +3/-1 marking scheme. Get an instant estimate of your raw score, percentage, and performance level.';
const slug = 'score-calculator';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        {
            '@type': 'Question',
            name: 'What is the marking scheme for UPSC CMS 2026?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'UPSC CMS follows a +3 for each correct answer and -1 for each incorrect answer. Unattempted questions carry zero marks. There is no negative marking for leaving a question blank.',
            },
        },
        {
            '@type': 'Question',
            name: 'How is the UPSC CMS final score calculated?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'The final score is calculated as: (Correct Answers x 3) - (Incorrect Answers x 1). Unattempted questions do not affect the score. The maximum possible raw score is Total Questions x 3.',
            },
        },
        {
            '@type': 'Question',
            name: 'Is there negative marking in UPSC CMS?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'Yes, UPSC CMS has negative marking of -1 mark for each wrong answer. Correct answers fetch +3 marks. It is therefore advisable to attempt only those questions you are confident about.',
            },
        },
        {
            '@type': 'Question',
            name: 'What is a good score in UPSC CMS for final selection?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'A score above 55-60% (roughly 198-216 marks out of 360 for Paper 1 and Paper 2 combined) is generally considered competitive. However, cut-offs vary each year based on difficulty and number of vacancies.',
            },
        },
    ],
};

export default function ScoreCalculatorPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'ScoreCalculator', path: '/tools/score-calculator' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        ScoreCalculator 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Use this free UPSC CMS Score Calculator to estimate your score from the official +3/-1 marking scheme.
                        Enter your correct, incorrect, and unattempted answers to instantly see your raw score,
                        percentage, accuracy, and a performance verdict.
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
                                percentage, accuracy, and a performance label. You can also use the total questions field to model
                                different exam papers or scenarios.
                            </p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p className="mt-2">
                                UPSC CMS uses a strict +3/-1 marking scheme. Negative marking means every wrong guess costs you
                                3 potential marks. Use this calculator to understand how much a single guess can change your final
                                result and to estimate your standing against expected cut-offs.
                            </p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            {
                                q: 'What is the marking scheme for UPSC CMS 2026?',
                                a: 'UPSC CMS follows a +3 for each correct answer and -1 for each incorrect answer. Unattempted questions carry zero marks. There is no negative marking for leaving a question blank.',
                            },
                            {
                                q: 'How is the UPSC CMS final score calculated?',
                                a: 'The final score is calculated as: (Correct Answers x 3) - (Incorrect Answers x 1). Unattempted questions do not affect the score. The maximum possible raw score is Total Questions x 3.',
                            },
                            {
                                q: 'Is there negative marking in UPSC CMS?',
                                a: 'Yes, UPSC CMS has negative marking of -1 mark for each wrong answer. Correct answers fetch +3 marks. It is therefore advisable to attempt only those questions you are confident about.',
                            },
                            {
                                q: 'What is a good score in UPSC CMS for final selection?',
                                a: 'A score above 55-60% (roughly 198-216 marks out of 360 for Paper 1 and Paper 2 combined) is generally considered competitive. However, cut-offs vary each year based on difficulty and number of vacancies.',
                            },
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
