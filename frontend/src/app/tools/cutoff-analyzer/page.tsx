import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import Breadcrumbs from '@/components/Breadcrumbs';
import { jsonLdString } from '@/lib/metadata';
import CutoffAnalyzer from './CutoffAnalyzer';
import { CUTOFF_MAX_MARKS, historicalCutoffs } from './cutoffModel';

const data = historicalCutoffs();
const years = Array.from(new Set(Object.values(data).flatMap((byYear) => Object.keys(byYear)))).sort();
const firstYear = years[0];
const latestYear = years[years.length - 1];
const latest = Object.entries(data)
    .filter(([, byYear]) => byYear[latestYear] != null)
    .map(([cat, byYear]) => `${cat} ~${byYear[latestYear]}`)
    .join(', ');

const title = 'UPSC CMS Cutoff Analyzer 2026 — Historical Cutoffs & Trend Estimate';
const description = `Analyze approximate UPSC CMS written cutoffs (out of ${CUTOFF_MAX_MARKS}) from ${firstYear} to ${latestYear} across categories, see the trend and get a simple next-cycle estimate.`;
const slug = 'cutoff-analyzer';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug, path: `/tools/${slug}` });

const faqs = [
    {
        q: `What was the UPSC CMS cutoff in ${latestYear}?`,
        a: `Approximate ${latestYear} written cutoffs (out of ${CUTOFF_MAX_MARKS}) from publicly available UPSC notices: ${latest}. Always verify the exact numbers in the official UPSC press release on upsc.gov.in.`,
    },
    {
        q: 'How is the UPSC CMS cutoff determined?',
        a: 'The cutoff is determined by UPSC based on total vacancies, category-wise reservations, number of candidates, and paper difficulty. Cutoffs are category-specific and usually rise gradually when more candidates score high.',
    },
    {
        q: 'How to estimate the next UPSC CMS cutoff?',
        a: `Use the Cutoff Analyzer on this page. It draws a straight-line trend through the approximate ${firstYear}-${latestYear} cutoffs. With only a few years of data the estimate has low confidence — use it as a planning aid only.`,
    },
    {
        q: 'Does the UPSC CMS cutoff change every year?',
        a: 'Yes, cutoffs change every year based on candidate performance, exam difficulty, and available posts. They usually move by small margins unless the exam pattern changes significantly.',
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

export default function CutoffAnalyzerPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Cutoff Analyzer', path: '/tools/cutoff-analyzer' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        Cutoff Analyzer 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Explore approximate UPSC CMS written cutoffs from {firstYear} to {latestYear} by category.
                        Use the interactive analyser to estimate the next cutoff and compare your expected score against
                        category-wise estimates.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <CutoffAnalyzer />

                    <h2 className="text-2xl font-bold mt-12 mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <p>
                                Select your category, optionally enter your expected written score out of {CUTOFF_MAX_MARKS}, and click
                                &quot;Analyse Cutoff Trends&quot;. The tool shows the {firstYear}–{latestYear} trend, a next-cycle estimate,
                                and how your score compares with it.
                            </p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p>
                                Cutoff awareness helps you set realistic targets and avoid last-minute panic. A small
                                margin above the cutoff still matters because rank lists can shift based on
                                tie-breaking policy and vacancies. Treat the estimate as a planning benchmark, not a guarantee.
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
