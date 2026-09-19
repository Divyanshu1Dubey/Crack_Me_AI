import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import CollegePredictor from './CollegePredictor';

const title = 'UPSC CMS College Predictor 2026 — Rank-wise Hospital & Department Prediction';
const description = 'Predict likely government hospitals and departments for UPSC CMS 2026 based on your rank and category. Free interactive college predictor for Medical Officers.';
const slug = 'college-predictor';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'How accurate is the UPSC CMS college predictor?', acceptedAnswer: { '@type': 'Answer', text: 'This predictor uses previous year category-wise closing ranks to estimate likely options. Actual cutoffs change yearly based on vacancies, exam difficulty, and candidate preferences. Treat predictions as indicative guidance only, and always verify with the official UPSC CMS notification.' } },
        { '@type': 'Question', name: 'Which hospitals can I get with a rank under 200 in UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'With an AIR under 200 in General (UR) category, high-confidence options include AIIMS New Delhi, JIPMER Puducherry, PGIMER Chandigarh, NIMHANS Bangalore, Safdarjung Hospital, and RML Hospital across core departments like General Medicine, Surgery, Radiology, and Obstetrics & Gynaecology.' } },
        { '@type': 'Question', name: 'Does category affect UPSC CMS hospital allocation?', acceptedAnswer: { '@type': 'Answer', text: 'Yes. UPSC CMS reserves seats by category — General (UR), OBC (NCL), SC, ST, and PwBD. Reserved-category candidates have separate closing ranks, and hospitals like AIIMS Delhi, PGIMER, and JIPMER also accept reserved-category candidates at different rank thresholds.' } },
    ],
};

export default function CollegePredictorPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'CollegePredictor', path: '/tools/college-predictor' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        CollegePredictor 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Estimate which government hospitals and departments are realistic options for you based on your
                        UPSC CMS rank, category, and previous year closing trends. Use the interactive predictor below
                        to explore high-confidence, moderate, and reach options.
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
                            <p>Enter your expected or secured All India Rank (AIR), select your category, and choose the exam year. The predictor will compare your rank against previous year category-wise closing ranks to classify hospitals into High Confidence, Moderate / On Border, and Reach bands. Use these bands to shortlist hospitals before filling your preference list in the UPSC CMS application.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p>UPSC CMS offers posts in top central government hospitals such as AIIMS New Delhi, PGIMER Chandigarh, JIPMER Puducherry, Safdarjung Hospital, and RML Delhi — along with secondary hospitals across India. Filling preferences without rank-based guidance often leads to suboptimal postings. A rank-wise predictor helps you prioritise hospitals and departments where you have a realistic chance.</p>
                        </div>
                    </div>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'How accurate is the UPSC CMS college predictor?', a: 'This predictor uses previous year category-wise closing ranks to estimate likely options. Actual cutoffs change yearly based on vacancies, exam difficulty, and candidate preferences. Treat predictions as indicative guidance only, and always verify with the official UPSC CMS notification.' },
                            { q: 'Which hospitals can I get with a rank under 200 in UPSC CMS?', a: 'With an AIR under 200 in General (UR) category, high-confidence options include AIIMS New Delhi, JIPMER Puducherry, PGIMER Chandigarh, NIMHANS Bangalore, Safdarjung Hospital, and RML Hospital across core departments like General Medicine, Surgery, Radiology, and Obstetrics & Gynaecology.' },
                            { q: 'Does category affect UPSC CMS hospital allocation?', a: 'Yes. UPSC CMS reserves seats by category — General (UR), OBC (NCL), SC, ST, and PwBD. Reserved-category candidates have separate closing ranks, and hospitals like AIIMS Delhi, PGIMER, and JIPMER also accept reserved-category candidates at different rank thresholds.' },
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
