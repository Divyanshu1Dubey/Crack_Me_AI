import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import PyqAttemptAnalyzer from './PyqAttemptAnalyzer';

const title = 'UPSC CMS PYQ Attempt Analyzer 2026 — Topic Mastery & Weak Areas';
const description = 'Analyze your UPSC CMS previous year question performance. Enter subject-wise attempt data to see topic mastery percentages, improvement areas, and accuracy trends.';
const slug = 'pyq-attempt-analyzer';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'How do I analyze my UPSC CMS PYQ performance?', acceptedAnswer: { '@type': 'Answer', text: 'Use our PYQ Attempt Analyzer above. Enter your topic-wise attempt data in the format "Topic Name, Correct Count, Total Questions" — one topic per line. The tool will calculate your accuracy, identify mastered topics (≥75%), and highlight areas that need improvement (<50%).' } },
        { '@type': 'Question', name: 'What accuracy should I aim for in UPSC CMS PYQs?', acceptedAnswer: { '@type': 'Answer', text: 'Aim for at least 75% accuracy on PYQs from all major topics before the exam. Topics scoring below 50% need immediate attention. Our analyzer categorizes topics into mastered (≥75%), intermediate (50-75%), and needs-work (<50%).' } },
        { '@type': 'Question', name: 'How many times should I attempt UPSC CMS PYQs?', acceptedAnswer: { '@type': 'Answer', text: 'Attempt each year\'s UPSC CMS paper at least twice — first without solutions to test yourself, then with solutions to learn. Our PYQ Attempt Analyzer helps you track improvement across multiple attempts by entering data for each round.' } },
    ],
};

export default function PyqAttemptAnalyzerPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'PYQ Attempt Analyzer', path: '/tools/pyq-attempt-analyzer' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS PYQ Attempt Analyzer
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Analyze your previous year question performance. Enter subject-wise attempt data to see topic mastery
                        percentages, identify improvement areas, and get recommendations for focused revision.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <PyqAttemptAnalyzer />

                    <h2 className="text-2xl font-bold mt-12 mb-4">How to Use This Analyzer</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">Step 1: Gather Your Data</h3>
                            <p>After solving a PYQ set or mock test, note down for each topic: the topic name, how many you got correct, and the total number of questions from that topic.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Step 2: Enter in the Format Above</h3>
                            <p>Use the format "Topic Name, Correct Count, Total Questions" — one topic per line. For example: "Cardiology, 8, 10" means you got 8 out of 10 Cardiology questions correct.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Step 3: Analyze and Act</h3>
                            <p>The tool categorizes topics into Mastered (≥75%), Intermediate (50-75%), and Needs Work (&lt;50%). Focus your revision on the "Needs Work" topics first.</p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'How do I analyze my UPSC CMS PYQ performance?', a: 'Use our PYQ Attempt Analyzer above. Enter topic-wise attempt data in the format "Topic Name, Correct Count, Total Questions" — one topic per line. The tool calculates accuracy, identifies mastered topics (≥75%), and highlights areas needing improvement (<50%).' },
                            { q: 'What accuracy should I aim for in UPSC CMS PYQs?', a: 'Aim for at least 75% accuracy on PYQs from all major topics before the exam. Topics scoring below 50% need immediate attention. Our analyzer categorizes topics into mastered (≥75%), intermediate (50-75%), and needs-work (<50%).' },
                            { q: 'How many times should I attempt UPSC CMS PYQs?', a: 'Attempt each year\'s UPSC CMS paper at least twice — first without solutions to test yourself, then with solutions to learn. Our analyzer helps track improvement across multiple attempts.' },
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
