import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import Breadcrumbs from '@/components/Breadcrumbs';
import { jsonLdString } from '@/lib/metadata';
import { UPSC_CMS_PATTERN } from '@/lib/examPatterns';
import MarksVsRankPredictor from './MarksVsRankPredictor';

const title = 'Marks Vs Rank Predictor 2026 — UPSC CMS Category-Wise Rank & Percentile';
const description = 'Get a rough, illustrative UPSC CMS rank estimate from expected marks with category-wise ranges, percentile estimates and strategy advice. Interactive calculator for General, OBC, SC and ST categories.';
const slug = 'marks-vs-rank-predictor';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug, path: `/tools/${slug}` });

const [paper1, paper2] = UPSC_CMS_PATTERN.papers;
const interviewShare = Math.round((UPSC_CMS_PATTERN.personalityTestMarks / UPSC_CMS_PATTERN.totalMarks) * 100);

const faqs = [
    {
        q: 'How is UPSC CMS rank calculated from marks?',
        a: `UPSC CMS merit is based on total marks across Paper I (General Medicine & Paediatrics, ${paper1.marks}), Paper II (Surgery, Gynaecology & Obstetrics and PSM, ${paper2.marks}) and the Personality Test (${UPSC_CMS_PATTERN.personalityTestMarks}) — ${UPSC_CMS_PATTERN.totalMarks} marks in all. UPSC does not publish score distributions, so our predictor places your marks on an assumed curve to give a rough, illustrative rank range and category-wise percentile.`,
    },
    {
        q: 'What is a good rank for UPSC CMS 2026?',
        a: 'A "good" rank depends on your category and the number of vacancies in that year\'s notice. Compare your estimated category rank with the posts available to your category (see the Category Rank Filter) and with recent cut-offs.',
    },
    {
        q: 'How much does the Personality Test affect the final rank?',
        a: `The Personality Test carries ${UPSC_CMS_PATTERN.personalityTestMarks} of the ${UPSC_CMS_PATTERN.totalMarks} total marks (about ${interviewShare}%). The written papers decide most of the merit, but a strong or weak interview can still move your rank noticeably. Use the predictor to see how different interview scores change your estimate.`,
    },
    {
        q: 'Does reservation affect my predicted rank?',
        a: 'Yes — the predictor adjusts percentile calculations based on your selected category. The overall percentile shows how you rank among all candidates, while the category percentile shows how you rank within your specific category. Category ranks are computed relative to an assumed pool size for each category, not the absolute total.',
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

export default function MarksVsRankPredictorPage() {
    return (
        <>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }}
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
                        Enter your expected marks for Paper I, Paper II and the Personality Test for a rough
                        estimate of your <strong>UPSC CMS 2026</strong> rank. Get category-wise rank ranges (General, OBC,
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
                                    Enter your expected marks for Paper I (General Medicine &amp; Paediatrics) out of {paper1.marks}
                                    {' '}and Paper II (Surgery, OBG &amp; PSM) out of {paper2.marks}.
                                </li>
                                <li>
                                    Add your anticipated Personality Test score out of {UPSC_CMS_PATTERN.personalityTestMarks}.
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
                                graduates appearing for a limited number of posts. Knowing where you roughly stand
                                helps you decide whether to prepare for one more attempt,
                                improve weak subjects, or start planning your interview preparation.
                                Use this tool alongside previous year trends and your mock-test performance
                                for a realistic picture.
                            </p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">UPSC CMS 2026 Score Structure</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li>{paper1.name} – General Medicine &amp; Paediatrics: {paper1.marks} marks</li>
                                <li>{paper2.name} – Surgery, Gynaecology &amp; Obstetrics, PSM: {paper2.marks} marks</li>
                                <li>Personality Test: {UPSC_CMS_PATTERN.personalityTestMarks} marks</li>
                                <li>Total: {UPSC_CMS_PATTERN.totalMarks} marks</li>
                            </ul>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {faqs.map((faq) => (
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
