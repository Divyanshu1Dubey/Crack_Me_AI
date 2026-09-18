import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import StudyPlanBuilder from './StudyPlanBuilder';

const title = 'Study Plan Builder — NEET PG / UPSC CMS / INI-CET | CrackCMS';
const description = 'Build a personalised study plan for NEET PG, UPSC CMS, or INI-CET. Enter your exam date, available hours, and weak subjects to get a day-by-day 6-month preparation schedule.';
const slug = 'study-plan-builder';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'How do I make a study plan for NEET PG?', acceptedAnswer: { '@type': 'Answer', text: 'Use the CrackCMS Study Plan Builder above — enter your exam date, available daily hours, and target exam (NEET PG / UPSC CMS / INI-CET). The tool generates a personalised day-by-day schedule based on your time horizon and weak subjects.' } },
        { '@type': 'Question', name: 'How many hours should I study daily for NEET PG?', acceptedAnswer: { '@type': 'Answer', text: 'Most NEET PG toppers study 8-10 hours/day in the final 3 months. In the foundation phase (months 1-6), 4-6 hours/day is sustainable. Use the Study Plan Builder to customise based on your schedule.' } },
    ],
};

export default function StudyPlanBuilderPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'Tools', path: '/tools' }, { name: 'Study Plan Builder', path: '/tools/study-plan-builder' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        Study Plan Builder
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Build a personalised day-by-day study plan for <strong>NEET PG</strong>, <strong>UPSC CMS</strong>, or <strong>INI-CET</strong>.
                        Enter your exam date, available daily hours, and weak subjects — the tool generates a complete schedule
                        with foundation, practice, and sprint phases.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <StudyPlanBuilder />

                    <h2 className="text-2xl font-bold mt-12 mb-4">Study Plan Tips</h2>
                    <div className="space-y-4 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">Phase 1: Foundation (first 40% of days)</h3>
                            <p>Cover all subjects once with standard textbooks. Focus on understanding concepts rather than memorising. Solve 30-50 MCQs per subject daily.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Phase 2: Practice (next 35% of days)</h3>
                            <p>Take full mock tests every week. Analyse every mistake. Spend extra time on weak subjects. Start time management practice (learn to solve 200 Qs in 180 min for INI-CET/NEET PG).</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Phase 3: Sprint (last 25% of days)</h3>
                            <p>Only mocks + rapid revision. No new topics. Review flashcards and mnemonics. Sleep well — no last-night cramming. Trust your preparation.</p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'How do I make a study plan for NEET PG?', a: 'Use the Study Plan Builder above — enter your exam date, available daily hours, and target exam. The tool generates a personalised schedule. Most NEET PG toppers follow an 8-10 hour/day routine in the final 3 months.' },
                            { q: 'How many hours should I study daily for NEET PG?', a: 'In the foundation phase (months 1-6), 4-6 hours/day is sustainable. In the final 3 months, increase to 8-10 hours/day. Use the Study Plan Builder to customise based on your schedule and weak subjects.' },
                            { q: 'What is the best preparation strategy for UPSC CMS?', a: 'UPSC CMS can be prepared in 6 months with focused effort. Start with subject-wise PYQs, take one full mock every Sunday, spend 30 minutes daily on AI tutor for weak topics, and revise mnemonics using spaced-repetition flashcards.' },
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
