import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import MarksVsRankPredictor from './MarksVsRankPredictor';

const title = 'Marks Vs Rank Predictor 2026 — UPSC CMS Category-Wise Rank & Percentile';
const description = 'Predict your UPSC CMS rank from expected marks with category-wise ranges, percentile estimates and strategy advice. Interactive calculator for General, OBC, SC and ST categories.';
const slug = 'marks-vs-rank-predictor';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        {
            '@type': 'Question',
            name: 'How is UPSC CMS rank calculated from marks?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'UPSC CMS merit is based on total marks across Paper I (General Medicine, 500), Paper II (Allied Subjects, 500) and Personality Test (800). Ranks are assigned after normalising scores across all candidates. Our predictor uses a statistical model based on historical score distributions to estimate your rank range and category-wise percentile.',
            },
        },
        {
            '@type': 'Question',
            name: 'What is a good rank for UPSC CMS 2026?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'A "good" rank depends on your category and the number of vacancies. In recent years, General category candidates with a rank under ~200 have had strong selection chances. OBC candidates benefit from category reservations, so ranks up to ~400-500 can be competitive. Use the predictor above with your expected marks to get a category-specific estimate.',
            },
        },
        {
            '@type': 'Question',
            name: 'How much does the Personality Test affect the final rank?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'The Personality Test carries 800 marks out of a total of 1800 (about 44% of total score). It has a very significant impact on your final rank. Candidates scoring 550+ in papers but underperforming in the interview often see their rank slip considerably. Use the predictor to see how different interview scores change your estimated rank.',
            },
        },
        {
            '@type': 'Question',
            name: 'Does reservation affect my predicted rank?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'Yes — the predictor adjusts percentile calculations based on your selected category. The overall percentile shows how you rank among all candidates, while the category percentile shows how you rank within your specific category. Category ranks are computed relative to the approximate pool size for each category, not the absolute total.',
            },
        },
    ],
};

export default function MarksVsRankPredictorPage() {
    return (
        <>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
            />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs
                        items={[
                            { name: 'UPSC CMS', path: '/cms' },
                            { name: 'Marks Vs Rank Predictor', path: '/tools/marks-vs-rank-predictor' },
                        ]}
                    />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        Marks Vs Rank Predictor 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Enter your expected marks for Paper I, Paper II and the Personality Test to estimate
                        your <strong>UPSC CMS 2026</strong> rank. Get category-wise rank ranges (General, OBC,
                        SC, ST), overall and category percentile estimates, and personalised strategy advice —
                        all computed client-side.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <MarksVsRankPredictor />

                    <h2 className="text-2xl font-bold mt-12 mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <ol className="mt-2 space-y-1 list-decimal pl-5">
                                <li>
                                    Enter your expected marks for Paper I (General Medicine) out of 500
                                    and Paper II (Allied Subjects) out of 500.
                                </li>
                                <li>
                                    Add your anticipated Personality Test score out of 800.
                                </li>
                                <li>
                                    Select your category (General, OBC, SC or ST) for a tailored
                                    percentile calculation.
                                </li>
                                <li>
                                    Click <strong>Predict Rank</strong> to see your estimated rank
                                    range, percentile and strategy advice.
                                </li>
                            </ol>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p>
                                UPSC CMS selection is highly competitive, with tens of thousands of MBBS
                                graduates appearing for a limited number of posts. Knowing where you stand
                                in terms of rank helps you decide whether to prepare for one more attempt,
                                improve weak subjects, or start planning your interview preparation.
                                Use this tool alongside previous year trends and your mock-test performance
                                for a realistic picture.
                            </p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">UPSC CMS 2026 Score Structure</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li>Paper I – General Medicine: 500 marks</li>
                                <li>Paper II – Allied Subjects: 500 marks</li>
                                <li>Personality Test / Interview: 800 marks</li>
                                <li>Total: 1800 marks</li>
                            </ul>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            {
                                q: 'How is UPSC CMS rank calculated from marks?',
                                a: 'UPSC CMS merit is based on total marks across Paper I (General Medicine, 500), Paper II (Allied Subjects, 500) and Personality Test (800). Ranks are assigned after normalising scores across all candidates. Our predictor uses a statistical model based on historical score distributions to estimate your rank range and category-wise percentile.',
                            },
                            {
                                q: 'What is a good rank for UPSC CMS 2026?',
                                a: 'A "good" rank depends on your category and the number of vacancies. In recent years, General category candidates with a rank under ~200 have had strong selection chances. OBC candidates benefit from category reservations, so ranks up to ~400-500 can be competitive. Use the predictor above with your expected marks to get a category-specific estimate.',
                            },
                            {
                                q: 'How much does the Personality Test affect the final rank?',
                                a: 'The Personality Test carries 800 marks out of a total of 1800 (about 44% of total score). It has a very significant impact on your final rank. Candidates scoring 550+ in papers but underperforming in the interview often see their rank slip considerably. Use the predictor to see how different interview scores change your estimated rank.',
                            },
                            {
                                q: 'Does reservation affect my predicted rank?',
                                a: 'Yes — the predictor adjusts percentile calculations based on your selected category. The overall percentile shows how you rank among all candidates, while the category percentile shows how you rank within your specific category. Category ranks are computed relative to the approximate pool size for each category, not the absolute total.',
                            },
                        ].map((faq) => (
                            <div
                                key={faq.q}
                                className="rounded-xl border border-border bg-card p-5"
                            >
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
