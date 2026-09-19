import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import MockTestAnalyzer from './MockTestAnalyzer';

const title = 'MockTestAnalyzer 2026 — Subject-wise UPSC CMS Mock Test Performance Tool';
const description = 'Analyze your UPSC CMS mock test performance subject-wise. Identify weak areas, track improvement trends, and get personalised study recommendations for Combined Medical Services 2026.';
const slug = 'mock-test-analyzer';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        {
            '@type': 'Question',
            name: 'How should I use mock test analysis for UPSC CMS preparation?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'After each mock test, enter your subject-wise percentage scores into MockTestAnalyzer. Review the weakest subjects and time spent, build a focused revision plan for those topics, and retake a targeted mock after 7-10 days to confirm improvement.',
            },
        },
        {
            '@type': 'Question',
            name: 'What is a good mock test score for UPSC CMS?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'A score above 65-70% in a full-length UPSC CMS mock test is generally a strong baseline. However, aim for above 80% in your strongest subjects and at least 60% across all subjects to build a safe margin before the actual exam.',
            },
        },
        {
            '@type': 'Question',
            name: 'Which subjects are most important for UPSC CMS mock test analysis?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'All UPSC CMS subjects matter because the paper tests breadth. Start analysis with high-weightage clinical subjects like General Medicine, General Surgery, Obstetrics & Gynaecology, Paediatrics, Preventive & Social Medicine, and then cover speciality subjects and para-clinicals.',
            },
        },
    ],
};

export default function MockTestAnalyzerPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'MockTestAnalyzer', path: '/tools/mock-test-analyzer' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        MockTestAnalyzer 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Track your UPSC CMS mock test performance subject-wise, spot weak areas fast, and
                        turn every mock attempt into a smarter revision plan.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <MockTestAnalyzer />

                    <h2 className="text-2xl font-bold mt-12 mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li>Take a full-length UPSC CMS mock test under timed conditions.</li>
                                <li>Enter your subject-wise scores into the analyzer above.</li>
                                <li>Review weakest subjects, overall score, and the personalised recommendation.</li>
                                <li>Plan targeted revision and retake a focused mock after 7-10 days to confirm improvement.</li>
                                <li>Repeat weekly to track progress and keep momentum high.</li>
                            </ul>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p className="mt-2">
                                UPSC CMS rewards consistent performance across all subjects. A single mock score is less
                                useful than a trend over time. This tool helps you convert raw mock results into an
                                actionable study strategy for <strong>{siteName}</strong> preparation.
                            </p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            {
                                q: 'How should I use mock test analysis for UPSC CMS preparation?',
                                a: 'After each mock test, enter your subject-wise percentage scores into MockTestAnalyzer. Review the weakest subjects and time spent, build a focused revision plan for those topics, and retake a targeted mock after 7-10 days to confirm improvement.',
                            },
                            {
                                q: 'What is a good mock test score for UPSC CMS?',
                                a: 'A score above 65-70% in a full-length UPSC CMS mock test is generally a strong baseline. However, aim for above 80% in your strongest subjects and at least 60% across all subjects to build a safe margin before the actual exam.',
                            },
                            {
                                q: 'Which subjects are most important for UPSC CMS mock test analysis?',
                                a: 'All UPSC CMS subjects matter because the paper tests breadth. Start analysis with high-weightage clinical subjects like General Medicine, General Surgery, Obstetrics & Gynaecology, Paediatrics, Preventive & Social Medicine, and then cover speciality subjects and para-clinicals.',
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
