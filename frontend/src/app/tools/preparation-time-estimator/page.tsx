import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import PreparationTimeEstimator from './PreparationTimeEstimator';

const title = 'UPSC CMS Preparation Time Estimator 2026 — How Many Months Do You Need?';
const description = 'Estimate how many months you need to prepare for UPSC CMS 2026. Based on current level, target rank, daily study hours, and weak subjects.';
const slug = 'preparation-time-estimator';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'How many months are needed for UPSC CMS preparation?', acceptedAnswer: { '@type': 'Answer', text: 'Most candidates need 4-8 months of focused preparation. Beginners with a top-1000 rank target typically need 7 months, while intermediate candidates need 4 months. Use our Preparation Time Estimator for a personalised estimate.' } },
        { '@type': 'Question', name: 'Can I crack UPSC CMS in 3 months?', acceptedAnswer: { '@type': 'Answer', text: '3 months is tight but possible if you are already at an intermediate/advanced level and can dedicate 6-8 hours daily. Focus on PYQs, high-yield topics, and full-length mocks. Our estimator can help you plan this intensive schedule.' } },
        { '@type': 'Question', name: 'What is the best daily study duration for UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'Most successful candidates study 6-8 hours daily. If you have more time available, you can accelerate your preparation. If you have less time, maximise weekends with full-length mock tests.' } },
    ],
};

export default function PreparationTimeEstimatorPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Preparation Time Estimator', path: '/tools/preparation-time-estimator' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Preparation Time Estimator
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Get a personalised estimate of how many months you need to prepare for UPSC CMS 2026.
                        Based on your current level, target rank, daily study hours, and weak subjects.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <PreparationTimeEstimator />

                    <h2 className="text-2xl font-bold mt-12 mb-4">How to Plan Your UPSC CMS Preparation</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">Phase 1: Foundation (first 40% of days)</h3>
                            <p>Cover all subjects once with standard textbooks. Focus on understanding concepts rather than memorising. Solve 30-50 MCQs per subject daily.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Phase 2: Practice (next 35% of days)</h3>
                            <p>Take full mock tests every week. Analyse every mistake. Spend extra time on weak subjects. Start time management practice.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Phase 3: Sprint (last 25% of days)</h3>
                            <p>Only mocks + rapid revision. No new topics. Review flashcards and mnemonics. Sleep well — no last-night cramming.</p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'How many months are needed for UPSC CMS preparation?', a: 'Most candidates need 4-8 months of focused preparation. Beginners with a top-1000 rank target typically need 7 months, while intermediate candidates need 4 months. Use our Preparation Time Estimator for a personalised estimate based on your specific situation.' },
                            { q: 'Can I crack UPSC CMS in 3 months?', a: '3 months is tight but possible if you are already at an intermediate/advanced level and can dedicate 6-8 hours daily. Focus on PYQs, high-yield topics, and full-length mocks.' },
                            { q: 'What is the best daily study duration for UPSC CMS?', a: 'Most successful candidates study 6-8 hours daily. If you have more time available, you can accelerate your preparation. If you have less time, maximise weekends with full-length mock tests.' },
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
