import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import CutoffAnalyzer from './CutoffAnalyzer';

const title = 'UPSC CMS Cutoff Analyzer 2026 — Historical Cutoffs & Prediction';
const description = 'Analyze UPSC CMS cutoff marks from 2018 to 2025 across General, OBC, SC, ST, EWS, and PwBD categories. View trends and get a data-driven 2026 cutoff prediction.';
const slug = 'cutoff-analyzer';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'What is the UPSC CMS cutoff for 2025?', acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS 2025 cutoff marks vary by category. For General it is 120/200, OBC-NCL 108/200, SC 95/200, ST 90/200, EWS 114/200, PwBD(OH) 86/200, and PwBD(HI) 84/200. Always verify against the official notification.' } },
        { '@type': 'Question', name: 'How is the UPSC CMS cutoff determined?', acceptedAnswer: { '@type': 'Answer', text: 'The cutoff is determined by UPSC based on total vacancies, category-wise reservations, number of candidates, and paper difficulty. Cutoffs are category-specific and usually rise gradually when more candidates score high.' } },
        { '@type': 'Question', name: 'How to predict UPSC CMS cutoff 2026?', acceptedAnswer: { '@type': 'Answer', text: 'Use the Cutoff Analyzer tool on this page. It applies trend-based estimation from 2018-2025 official cutoff data. Note that predictions are planning aids only and actual cutoffs may change due to exam pattern or vacancies.' } },
        { '@type': 'Question', name: 'Does the UPSC CMS cutoff change every year?', acceptedAnswer: { '@type': 'Answer', text: 'Yes, cutoffs change every year based on candidate performance, exam difficulty, and available posts. They usually move by small margins unless the exam pattern changes significantly.' } },
    ],
};

export default function CutoffAnalyzerPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'CutoffAnalyzer', path: '/tools/cutoff-analyzer' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        CutoffAnalyzer 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Explore UPSC CMS historical cutoff trends from 2018 to 2025 across all reservation categories.
                        Use the interactive analyser to estimate the 2026 cutoff and compare your expected score against
                        predicted category-wise thresholds.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <CutoffAnalyzer />

                    <h2 className="text-2xl font-bold mt-12 mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <p>
                                Select your category, optionally enter your expected score out of 200, and click
                                &quot;Analyse Cutoff Trends&quot;. The tool shows the 2018–2025 official cutoff trend, a 2026 prediction,
                                and guidance on how your score compares to the predicted threshold.
                            </p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p>
                                Cutoff awareness helps you set realistic targets and avoid last-minute panic. A small
                                margin above the cutoff still matters because rank lists can shift based on normalization,
                                tie-breaking policy, and vacancies. Treat the prediction as a planning benchmark, not a guarantee.
                            </p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'What is the UPSC CMS cutoff for 2025?', a: 'UPSC CMS 2025 cutoff marks vary by category. For General it is 120/200, OBC-NCL 108/200, SC 95/200, ST 90/200, EWS 114/200, PwBD(OH) 86/200, and PwBD(HI) 84/200. Always verify against the official notification.' },
                            { q: 'How is the UPSC CMS cutoff determined?', a: 'The cutoff is determined by UPSC based on total vacancies, category-wise reservations, number of candidates, and paper difficulty. Cutoffs are category-specific and usually rise gradually when more candidates score high.' },
                            { q: 'How to predict UPSC CMS cutoff 2026?', a: 'Use the Cutoff Analyzer tool above. It applies trend-based estimation from 2018-2025 official cutoff data. Predictions are planning aids only and actual cutoffs may change due to exam pattern or vacancies.' },
                            { q: 'Does the UPSC CMS cutoff change every year?', a: 'Yes, cutoffs change every year based on candidate performance, exam difficulty, and available posts. They usually move by small margins unless the exam pattern changes significantly.' },
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
