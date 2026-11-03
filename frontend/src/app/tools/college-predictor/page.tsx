import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import CollegePredictor from './CollegePredictor';
import { UPSC_CMS_CYCLE } from '@/lib/examPatterns';
import { jsonLdString } from '@/lib/metadata';

const title = 'UPSC CMS College Predictor 2026 — Which Service Can Your Rank Get?';
const description = 'Rank-based estimate of the UPSC CMS 2026 service you may get: CHS GDMO (Category I), or Railways ADMO, NDMC GDMO or MCD GDMO Gr-II (Category II). Illustrative thresholds, not official closing ranks.';
const slug = 'college-predictor';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug, path: `/tools/${slug}` });

// UPSC CMS fills general-duty posts in four services; it does not recruit
// for AIIMS, PGIMER, JIPMER or NIMHANS (they recruit separately). The FAQ
// and the predictor used to claim otherwise.
const FAQS = [
    {
        q: 'How accurate is the UPSC CMS college predictor?',
        a: `It uses illustrative rank thresholds, not official UPSC closing ranks: each category's threshold is its share of the ${UPSC_CMS_CYCLE.vacancies.toLocaleString('en-IN')} posts advertised for ${UPSC_CMS_CYCLE.year}. Actual cutoffs change yearly with vacancies, exam difficulty and candidate preferences, so treat the result as indicative only and verify with the official UPSC CMS notification.`,
    },
    {
        q: 'Which posts does UPSC CMS fill?',
        a: 'Category I is the General Duty Medical Officer (GDMO) sub-cadre of the Central Health Service. Category II is Assistant Divisional Medical Officer (ADMO) in the Railways, General Duty Medical Officer in the New Delhi Municipal Council and General Duty Medical Officer Gr-II in the Municipal Corporation of Delhi. These are general-duty posts; AIIMS, PGIMER, JIPMER and NIMHANS recruit separately and are not filled through UPSC CMS.',
    },
    {
        q: 'Does category affect UPSC CMS allocation?',
        a: 'Yes. Posts are reserved by category — General (UR), EWS, OBC (NCL), SC, ST and PwBD — and each service has its own category-wise vacancies, so the last rank that gets a given service differs by category and by service.',
    },
];

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQS.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
};

export default function CollegePredictorPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'College Predictor', path: '/tools/college-predictor' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Service Predictor 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Estimate whether your rank is likely to get one of the UPSC CMS services — CHS GDMO
                        (Category I), or Railways ADMO, NDMC GDMO and MCD GDMO Gr-II (Category II) — based on your
                        category. It uses illustrative rank thresholds, not official UPSC closing ranks.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-10 sm:px-6">
                    <CollegePredictor />
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <p>Enter your expected or secured rank (your All India Rank for General, or your rank within your category&apos;s list) and select your category. The predictor compares it with an illustrative threshold for your category — its share of the advertised vacancies — and places the UPSC CMS services in a High Confidence, Moderate / On Border or Reach band. Use it as a rough guide before filling your service preferences.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p>UPSC CMS recruits for four services: the Central Health Service (GDMO sub-cadre, Category I), and Railways ADMO, NDMC GDMO and MCD GDMO Gr-II (Category II). Posts are allocated by rank and your preference order, and each service has its own category-wise vacancies, so knowing roughly where your rank stands helps you order your preferences realistically.</p>
                        </div>
                    </div>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {FAQS.map((faq) => (
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
