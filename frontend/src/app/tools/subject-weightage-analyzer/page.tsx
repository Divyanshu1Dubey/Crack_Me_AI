import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import Breadcrumbs from '@/components/Breadcrumbs';
import { jsonLdString } from '@/lib/metadata';
import { UPSC_CMS_PATTERN } from '@/lib/examPatterns';
import SubjectWeightageAnalyzer from './SubjectWeightageAnalyzer';
import { officialCmsWeightage } from './weightage';

const title = 'UPSC CMS Subject Weightage Analyzer 2026 — Subject-wise Question Split';
const description = 'See how UPSC CMS questions are split by subject (Medicine 96, Paediatrics 24, Surgery, OBG and PSM 40 each) and plan your study hours by weightage.';
const slug = 'subject-weightage-analyzer';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug, path: `/tools/${slug}` });

const weights = officialCmsWeightage();
const byName = (name: string) => weights.find((w) => w.subject === name);
const medicine = byName('General Medicine');
const paediatrics = byName('Paediatrics');
const surgery = byName('Surgery');

const faqs = [
    {
        q: 'Which subject has the highest weightage in UPSC CMS?',
        a: `General Medicine: ${medicine?.questions} of ${UPSC_CMS_PATTERN.totalQuestions} questions (${medicine?.sharePct}%), all in Paper I, including Cardiology, Neurology, Dermatology and Psychiatry. Surgery, Gynaecology & Obstetrics and PSM carry ${surgery?.questions} questions each (${surgery?.sharePct}%) in Paper II, and Paediatrics ${paediatrics?.questions} (${paediatrics?.sharePct}%) in Paper I.`,
    },
    {
        q: 'How should I use subject weightage to plan my preparation?',
        a: 'Split your study hours roughly in proportion to each subject\'s share of questions (the tool above does this for your weekly hours), then adjust for your weak areas using topic-wise PYQ practice.',
    },
    {
        q: 'Does the subject split change every year?',
        a: 'The subject-wise question split is set in the UPSC CMS notice and has been stable; the topics asked within each subject vary from year to year. Always check the current notification on upsc.gov.in.',
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

export default function SubjectWeightageAnalyzerPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Subject Weightage Analyzer', path: '/tools/subject-weightage-analyzer' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Subject Weightage Analyzer 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        See how the UPSC CMS paper is weighted by subject and turn your weekly study hours into a
                        subject-wise plan. Prioritize your preparation by the marks each subject actually carries.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <SubjectWeightageAnalyzer />

                    <h2 className="text-2xl font-bold mt-12 mb-4">UPSC CMS Subject-wise Weightage Breakdown</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">Paper I</h3>
                            <p>General Medicine ({medicine?.questions} questions, {medicine?.sharePct}% of the exam) and Paediatrics ({paediatrics?.questions} questions, {paediatrics?.sharePct}%).</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Paper II</h3>
                            <p>Surgery (including ENT, Ophthalmology, Traumatology and Orthopaedics), Gynaecology &amp; Obstetrics and Preventive &amp; Social Medicine — {surgery?.questions} questions each ({surgery?.sharePct}% each).</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Study Strategy</h3>
                            <p>Medicine alone is worth as much as Surgery and PSM together, so it deserves the largest share of your time. Combine this split with our Study Plan Builder for a personalised schedule.</p>
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
