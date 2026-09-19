import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import ExamReadinessScore from './ExamReadinessScore';

const title = 'UPSC CMS Exam Readiness Score 2026 — How Prepared Are You?';
const description = 'Calculate your UPSC CMS 2026 exam readiness with our interactive tool. Assess syllabus completion, mock test performance, revision cycles, and study hours to get a personalised readiness score.';
const slug = 'exam-readiness-score';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        {
            '@type': 'Question',
            name: 'What is a good UPSC CMS exam readiness score?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'A readiness score of 80+ indicates strong preparation: high syllabus coverage, multiple revision cycles, and consistent mock test practice. Scores between 60-79 suggest you are progressing well but should focus on weak subjects and more timed practice. Below 60 means you need a structured sprint plan before the exam.',
            },
        },
        {
            '@type': 'Question',
            name: 'How many mock tests should I take before UPSC CMS?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'Aim for at least 15-20 full-length subject-wise and grand mock tests before the exam. Mock tests build stamina, expose gaps, and improve time management. Review every mock thoroughly to turn mistakes into learning.',
            },
        },
        {
            '@type': 'Question',
            name: 'How many revision cycles are enough for UPSC CMS?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'Most successful candidates complete 3-4 revision cycles of the entire syllabus before the exam. Use spaced repetition, flashcards, and high-yield notes to make each revision faster and more effective than the last.',
            },
        },
        {
            '@type': 'Question',
            name: 'How can I improve my UPSC CMS readiness score quickly?',
            acceptedAnswer: {
                '@type': 'Answer',
                text: 'Focus on incomplete high-weightage subjects first, increase daily study hours, and take more mock tests. Prioritise revision over new topics in the final month. Use our readiness tool to track progress every week.',
            },
        },
    ],
};

export default function ExamReadinessScorePage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'ExamReadinessScore', path: '/tools/exam-readiness-score' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        ExamReadinessScore 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Assess your UPSC CMS preparation with a personalised readiness score.
                        Track syllabus completion, mock test performance, revision cycles, and daily study hours
                        to understand where you stand and what to improve before <strong>02 August 2026</strong>.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <ExamReadinessScore />

                    <h2 className="text-2xl font-bold mt-12 mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li>Enter days remaining until the exam and your daily study hours.</li>
                                <li>Record the number of mock tests you have completed.</li>
                                <li>Enter how many full revision cycles you have finished.</li>
                                <li>Adjust the subject-wise completion sliders to match your progress.</li>
                                <li>Click <strong>Calculate Readiness Score</strong> to get a score out of 100 and personalised advice.</li>
                            </ul>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p>
                                Readiness scoring turns vague feelings of "I am not prepared enough" into concrete, actionable insight.
                                It helps you prioritise incomplete subjects, plan final-week revision, and track improvement over time.
                                Use it weekly to stay accountable and adjust your strategy before the exam.
                            </p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            {
                                q: 'What is a good UPSC CMS exam readiness score?',
                                a: 'A readiness score of 80+ indicates strong preparation: high syllabus coverage, multiple revision cycles, and consistent mock test practice. Scores between 60-79 suggest you are progressing well but should focus on weak subjects and more timed practice. Below 60 means you need a structured sprint plan before the exam.',
                            },
                            {
                                q: 'How many mock tests should I take before UPSC CMS?',
                                a: 'Aim for at least 15-20 full-length subject-wise and grand mock tests before the exam. Mock tests build stamina, expose gaps, and improve time management. Review every mock thoroughly to turn mistakes into learning.',
                            },
                            {
                                q: 'How many revision cycles are enough for UPSC CMS?',
                                a: 'Most successful candidates complete 3-4 revision cycles of the entire syllabus before the exam. Use spaced repetition, flashcards, and high-yield notes to make each revision faster and more effective than the last.',
                            },
                            {
                                q: 'How can I improve my UPSC CMS readiness score quickly?',
                                a: 'Focus on incomplete high-weightage subjects first, increase daily study hours, and take more mock tests. Prioritise revision over new topics in the final month. Use our readiness tool to track progress every week.',
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
