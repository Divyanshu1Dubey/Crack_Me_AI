import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import { ArrowRight } from 'lucide-react';
import Script from 'next/script';

export const metadata: Metadata = {
    title: 'UPSC CMS vs INI-CET — Which is Better for MD/MS After MBBS?',
    description: 'UPSC CMS vs INI-CET: Compare government Medical Officer posts (UPSC CMS) vs AIIMS/PGI PG seats (INI-CET). Salary, exam pattern, difficulty, career growth, and which exam matches your goals.',
    alternates: { canonical: '/cms/vs-ini-cet', languages: { 'en-IN': '/cms/vs-ini-cet' } },
    openGraph: {
        type: 'article',
        url: '/cms/vs-ini-cet',
        title: 'UPSC CMS vs INI-CET — Which is Better for MD/MS After MBBS?',
        description: 'Compare government MO posts vs AIIMS/PGI PG seats. Salary, pattern, difficulty, career growth.',
        siteName,
        images: [{ url: '/cms-circle-logo.png', width: 1200, height: 630, alt: 'UPSC CMS vs INI-CET' }],
    },
    twitter: { card: 'summary_large_image', title: 'UPSC CMS vs INI-CET', description: 'Compare government MO posts vs AIIMS/PGI PG seats.' },
    robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'Which is better, UPSC CMS or INI-CET?', acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS gives you a central government Medical Officer post (Railways, CHS, ESIC) with stable salary from day one. INI-CET gives you an MD/MS at AIIMS, PGI, JIPMER, NIMHANS, SCTIMST with higher brand value. Choose CMS for job security; choose INI-CET for academic/research careers.' } },
        { '@type': 'Question', name: 'Can I prepare for UPSC CMS and INI-CET together?', acceptedAnswer: { '@type': 'Answer', text: 'Yes — both exams overlap ~60% in syllabus (Medicine, Surgery, OBG, PSM). INI-CET is more conceptual and image-based, while CMS is more memory-based. Many candidates use CMS prep as a base and add INI-CET-specific image-based practice.' } },
        { '@type': 'Question', name: 'Which pays more, UPSC CMS or INI-CET?', acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS gives ₹80k-₹1.2L/month from day one as a Medical Officer. INI-CET (MD/MS at AIIMS) gives ₹90k-₹1.1L/month stipend during residency, with much higher long-term earnings as a specialist in private practice or academia.' } },
    ],
};

export default function CMSVsINICETPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'CMS vs INI-CET', path: '/cms/vs-ini-cet' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS vs INI-CET — Government Job vs AIIMS PG
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        After MBBS, you can either go for <strong>UPSC CMS</strong> (a central government Medical Officer
                        post via UPSC) or <strong>INI-CET</strong> (an MD/MS seat at AIIMS, PGI, JIPMER, NIMHANS, SCTIMST
                        via AIIMS). Both are prestigious, but they lead to fundamentally different careers.
                        Here is a detailed comparison.
                    </p>

                    <div className="mt-8 grid gap-6 sm:grid-cols-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose UPSC CMS if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want a stable government job from day one (₹80k-₹1.2L)</li>
                                <li>You prefer job security, pension, and government perks over clinical practice</li>
                                <li>You want to work in Railways, CHS, ESIC, or central health services</li>
                                <li>You don't want to invest 3 years in residency for an MD/MS</li>
                            </ul>
                        </div>
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose INI-CET if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want an MD/MS from AIIMS, PGI, JIPMER, NIMHANS, or SCTIMST</li>
                                <li>You want academic, research, or superspecialisation track</li>
                                <li>You are comfortable with conceptual, image-heavy questions</li>
                                <li>You want the brand value of a central institute on your resume</li>
                            </ul>
                        </div>
                    </div>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-6">Side-by-Side Comparison</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse rounded-xl border border-border overflow-hidden">
                            <thead>
                                <tr className="bg-muted">
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Parameter</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">UPSC CMS</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">INI-CET</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Conducting body</td><td className="border border-border px-4 py-3">UPSC</td><td className="border border-border px-4 py-3">AIIMS New Delhi</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Frequency</td><td className="border border-border px-4 py-3">Once a year (Aug)</td><td className="border border-border px-4 py-3">Twice a year (Jan + Jul)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Pattern</td><td className="border border-border px-4 py-3">240 MCQs, 2 papers, 2 hrs each, 960 marks</td><td className="border border-border px-4 py-3">200 MCQs, 1 paper, 3 hours, 200 marks</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Negative marking</td><td className="border border-border px-4 py-3">-0.33 per wrong answer</td><td className="border border-border px-4 py-3">-1/3 per wrong answer</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Mode</td><td className="border border-border px-4 py-3">Offline (pen-and-paper OMR)</td><td className="border border-border px-4 py-3">CBT (online)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Outcome</td><td className="border border-border px-4 py-3">Medical Officer / GDMO post</td><td className="border border-border px-4 py-3">MD/MS seat at INIs</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Starting income</td><td className="border border-border px-4 py-3">₹80k-₹1.2L from day one</td><td className="border border-border px-4 py-3">₹90k-₹1.1L stipend during residency</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Long-term earnings</td><td className="border border-border px-4 py-3">₹1.5L-₹2L (govt peak)</td><td className="border border-border px-4 py-3">₹5L-₹50L+ (clinical + academic)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Prep time</td><td className="border border-border px-4 py-3">6 months typical</td><td className="border border-border px-4 py-3">6-12 months typical</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Seats</td><td className="border border-border px-4 py-3">~1,000-1,500 MO posts</td><td className="border border-border px-4 py-3">~1,000-1,500 PG seats</td></tr>
                            </tbody>
                        </table>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'Which is better, UPSC CMS or INI-CET?', a: 'UPSC CMS gives you a central government Medical Officer post with stable salary from day one. INI-CET gives you an MD/MS at AIIMS, PGI, JIPMER with higher brand value. Choose CMS for job security; choose INI-CET for academic/research careers and long-term earning potential.' },
                            { q: 'Can I prepare for UPSC CMS and INI-CET together?', a: 'Yes — both exams overlap ~60% in syllabus (Medicine, Surgery, OBG, PSM). INI-CET is more conceptual and image-based, while CMS is more memory-based. Many candidates use CMS prep as a base and add INI-CET-specific image-based practice.' },
                            { q: 'Which pays more, UPSC CMS or INI-CET?', a: 'UPSC CMS gives ₹80k-₹1.2L/month from day one. INI-CET (MD/MS at AIIMS) gives ₹90k-₹1.1L/month stipend during 3-year residency, with much higher long-term earnings as a specialist in private practice or academia.' },
                            { q: 'Is UPSC CMS easier than INI-CET?', a: 'UPSC CMS is generally considered easier — 240 MCQs across 2 papers with mild negative marking (-0.33). INI-CET has 200 MCQs in 3 hours with -1/3 negative marking and more conceptual/image-based questions. CMS can be prepared in 6 months; INI-CET typically needs 6-12 months.' },
                        ].map((faq) => (
                            <div key={faq.q} className="rounded-xl border border-border bg-card p-5">
                                <h3 className="font-bold text-sm">{faq.q}</h3>
                                <p className="mt-2 text-sm text-muted-foreground">{faq.a}</p>
                            </div>
                        ))}
                    </div>

                    <div className="mt-12 grid gap-6 sm:grid-cols-2">
                        <Link href="/cms" className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold uppercase tracking-wider text-muted-foreground">UPSC CMS</p>
                            <p className="mt-2 font-semibold group-hover:underline">Prepare for UPSC CMS <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">1,920+ PYQs, AI tutor, mock tests, exam simulator for central government MO posts.</p>
                        </Link>
                        <Link href="/ini-cet" className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold uppercase tracking-wider text-muted-foreground">INI-CET</p>
                            <p className="mt-2 font-semibold group-hover:underline">Prepare for INI-CET <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">12,000+ PYQs for AIIMS, PGI, JIPMER, NIMHANS. CBT mocks, rank predictor, AI tutor.</p>
                        </Link>
                    </div>
                </section>
            </div>
        </>
    );
}
