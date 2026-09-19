import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import SubjectWeightageAnalyzer from './SubjectWeightageAnalyzer';

const title = 'UPSC CMS Subject Weightage Analyzer 2026 — Topic-wise PYQ Analysis';
const description = 'Analyze topic and chapter-wise weightage in UPSC CMS from previous year questions (2018-2025). Know which topics carry the most marks and prioritize accordingly.';
const slug = 'subject-weightage-analyzer';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'Which subject has the highest weightage in UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'General Medicine and General Surgery typically carry the highest weightage in UPSC CMS, each contributing around 30-35% of the total questions. Paediatrics, OBG, and PSM follow with 10-15% each.' } },
        { '@type': 'Question', name: 'How do I analyze UPSC CMS previous year question weightage?', acceptedAnswer: { '@type': 'Answer', text: 'Use our Subject Weightage Analyzer above. It breaks down each subject into topics and shows the percentage weightage, number of questions asked, and whether the topic is trending up, down, or stable based on 2018-2025 data.' } },
        { '@type': 'Question', name: 'Which topics in UPSC CMS are most frequently asked?', acceptedAnswer: { '@type': 'Answer', text: 'High-frequency topics include Cardiology (General Medicine), GI Surgery (General Surgery), Obstetrics (OBG), Epidemiology (PSM), and Growth & Development (Paediatrics). These consistently appear with 12-14% weightage each.' } },
    ],
};

export default function SubjectWeightageAnalyzerPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Subject Weightage Analyzer', path: '/tools/subject-weightage-analyzer' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Subject Weightage Analyzer 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Discover the most important topics and chapters in UPSC CMS based on PYQ analysis from 2018-2025.
                        Prioritize your preparation by understanding which subjects and topics carry the most marks.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <SubjectWeightageAnalyzer />

                    <h2 className="text-2xl font-bold mt-12 mb-4">UPSC CMS Subject-wise Weightage Breakdown</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">High Weightage Subjects</h3>
                            <p>General Medicine (~25%), General Surgery (~20%), Paediatrics (~12%), OBG (~12%), and PSM (~10%) together cover approximately 80% of the UPSC CMS paper. Focus on these first.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Trending Topics</h3>
                            <p>Topics marked with an upward trend (↑) have seen increasing questions in recent years. These include Cardiology, Endocrinology, Biostatistics, and Vaccination. Allocate extra study time to these emerging areas.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Study Strategy</h3>
                            <p>Use the weightage percentages above to allocate your study time proportionally. A topic with 14% weightage deserves roughly 3x the study time of a topic with 5% weightage. Combine this with our Study Plan Builder for a personalised schedule.</p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'Which subject has the highest weightage in UPSC CMS?', a: 'General Medicine and General Surgery typically carry the highest weightage in UPSC CMS, each contributing around 30-35% of the total questions. Paediatrics, OBG, and PSM follow with 10-15% each. Use our Subject Weightage Analyzer for detailed breakdowns.' },
                            { q: 'How do I analyze UPSC CMS previous year question weightage?', a: 'Use our Subject Weightage Analyzer tool above. It breaks down each subject into individual topics and shows the percentage weightage, number of questions asked historically, and whether the topic is trending up, down, or stable based on 2018-2025 data.' },
                            { q: 'Which topics in UPSC CMS are most frequently asked?', a: 'High-frequency topics include Cardiology (General Medicine), GI Surgery (General Surgery), Obstetrics (OBG), Epidemiology (PSM), and Growth & Development (Paediatrics). These consistently appear with 12-14% weightage each year.' },
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
