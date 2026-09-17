import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import { ArrowRight } from 'lucide-react';
import Script from 'next/script';

export const metadata: Metadata = {
    title: 'NEET PG vs UPSC CMS — Which is Better? (2026 Comparison)',
    description: 'NEET PG vs UPSC CMS: Which exam should you choose after MBBS? Compare syllabus, difficulty, salary, career growth, exam pattern, and which one matches your goals.',
    alternates: { canonical: '/neet-pg/vs-upsc-cms', languages: { 'en-IN': '/neet-pg/vs-upsc-cms' } },
    openGraph: {
        type: 'article',
        url: '/neet-pg/vs-upsc-cms',
        title: 'NEET PG vs UPSC CMS — Which is Better? (2026 Comparison)',
        description: 'NEET PG vs UPSC CMS: Compare syllabus, difficulty, salary, career growth, exam pattern, and which exam matches your goals.',
        siteName,
        images: [{ url: '/cms-circle-logo.png', width: 1200, height: 630, alt: 'NEET PG vs UPSC CMS' }],
    },
    twitter: { card: 'summary_large_image', title: 'NEET PG vs UPSC CMS — Which is Better?', description: 'Compare syllabus, difficulty, salary, and career growth.' },
    robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'Which is better, NEET PG or UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'It depends on your career goals. NEET PG is better if you want clinical MD/MS specialisation and long-term earning potential. UPSC CMS is better if you want a stable government job with work-life balance from day one without spending 3 years in residency.' } },
        { '@type': 'Question', name: 'Can I prepare for NEET PG and UPSC CMS together?', acceptedAnswer: { '@type': 'Answer', text: 'Yes — the two exams overlap ~70% in syllabus. Most candidates use NEET PG prep as a base and add UPSC-CMS-specific PSM and Surgery depth. Both exams are around 6 months apart, allowing back-to-back attempts.' } },
        { '@type': 'Question', name: 'Which pays more, NEET PG or UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'NEET PG leads to clinical specialisation with much higher long-term earnings (₹20L-₹1Cr+ in private practice). UPSC CMS gives a stable ₹80k-₹1.2L government salary from day one with excellent job security.' } },
    ],
};

export default function NEETPGVsUPSCPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'NEET PG', path: '/neet-pg' }, { name: 'NEET PG vs UPSC CMS', path: '/neet-pg/vs-upsc-cms' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        NEET PG vs UPSC CMS — Which is Better After MBBS?
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        After MBBS, the two most common career routes are <strong>NEET PG</strong> (for MD/MS clinical
                        specialisation) and <strong>UPSC CMS</strong> (for central government Medical Officer posts).
                        Both are government-conducted exams, but they lead to fundamentally different careers.
                        Here is a detailed comparison to help you decide.
                    </p>

                    <div className="mt-8 grid gap-6 sm:grid-cols-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose NEET PG if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want a clinical MD/MS in a specific branch (Medicine, Surgery, Radiology)</li>
                                <li>You want to become a superspecialist later (DM/MCh)</li>
                                <li>You are willing to invest 3 years of residency for long-term growth</li>
                                <li>You want private practice or hospital consultant track</li>
                            </ul>
                        </div>
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose UPSC CMS if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want a stable government medical officer post (Railways, CHS, ESIC)</li>
                                <li>You prefer a non-clinical or administrative career path</li>
                                <li>You want work-life balance from day one without 3 years of residency</li>
                                <li>You value job security, pension, and government perks</li>
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
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">NEET PG</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">UPSC CMS</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Conducting body</td><td className="border border-border px-4 py-3">NBE (National Board of Examinations)</td><td className="border border-border px-4 py-3">UPSC</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Frequency</td><td className="border border-border px-4 py-3">Once a year</td><td className="border border-border px-4 py-3">Once a year</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Exam pattern</td><td className="border border-border px-4 py-3">200 MCQs, single paper, 3.5 hours, 800 marks</td><td className="border border-border px-4 py-3">240 MCQs, 2 papers, 2 hrs each, 960 marks</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Negative marking</td><td className="border border-border px-4 py-3">No</td><td className="border border-border px-4 py-3">Yes (-0.33 per wrong answer)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Mode</td><td className="border border-border px-4 py-3">Computer-Based Test (CBT)</td><td className="border border-border px-4 py-3">Offline (pen-and-paper OMR)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Subjects</td><td className="border border-border px-4 py-3">All 19 pre-clinical, para-clinical, clinical subjects</td><td className="border border-border px-4 py-3">Medicine, Surgery, Paediatrics, OBG, PSM + minor subjects</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Difficulty</td><td className="border border-border px-4 py-3">Hard (depth + breadth across 19 subjects)</td><td className="border border-border px-4 py-3">Moderate (clinic-heavy, less depth)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Success rate</td><td className="border border-border px-4 py-3">~50% qualify for counselling, ~10% get top branch</td><td className="border border-border px-4 py-3">~1-3% of applicants qualify</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Outcome</td><td className="border border-border px-4 py-3">MD/MS seat (residency)</td><td className="border border-border px-4 py-3">Medical Officer / GDMO post</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Starting income</td><td className="border border-border px-4 py-3">₹70k-₹1L stipend during 3-year residency</td><td className="border border-border px-4 py-3">₹80k-₹1.2L from day one</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Long-term earnings</td><td className="border border-border px-4 py-3">₹20L-₹1Cr+ (private practice + consultant)</td><td className="border border-border px-4 py-3">₹1.5L-₹2L (govt scale, peak at DGHS)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Career ceiling</td><td className="border border-border px-4 py-3">Prof, HOD, superspecialist, hospital consultant</td><td className="border border-border px-4 py-3">CMO, ADG, DGHS</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Prep time</td><td className="border border-border px-4 py-3">12-18 months typical</td><td className="border border-border px-4 py-3">6 months typical</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Total cost</td><td className="border border-border px-4 py-3">₹2-15L (coaching + materials)</td><td className="border border-border px-4 py-3">₹50k-₹2L (books + test series)</td></tr>
                            </tbody>
                        </table>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Syllabus Overlap</h2>
                    <p className="text-muted-foreground mb-4">
                        NEET PG and UPSC CMS share approximately <strong>70% syllabus overlap</strong>. The key differences:
                    </p>
                    <ul className="space-y-2 text-muted-foreground">
                        <li><strong>NEET PG covers all 19 subjects</strong> (pre-clinical, para-clinical, clinical) — very broad.</li>
                        <li><strong>UPSC CMS focuses on 5 main subjects</strong> (Medicine, Surgery, Paediatrics, OBG, PSM) — deeper in fewer topics.</li>
                        <li><strong>PSM weightage is higher in CMS</strong> (~17% of Paper II) compared to NEET PG.</li>
                        <li><strong>Surgery and OBG are more clinic-heavy in CMS</strong> — fewer anatomy/physiology questions.</li>
                    </ul>
                    <p className="mt-4 text-sm text-muted-foreground">
                        <strong>Strategy:</strong> If you are preparing for NEET PG, you already cover most of the CMS syllabus.
                        Add focused PSM revision and surgery/OBG clinic-based MCQs, and you can attempt CMS as a backup
                        in the same year.
                    </p>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'Which is better, NEET PG or UPSC CMS?', a: 'It depends on your career goals. NEET PG is better if you want clinical MD/MS specialisation and long-term earning potential. UPSC CMS is better if you want a stable government job with work-life balance from day one without spending 3 years in residency.' },
                            { q: 'Can I prepare for NEET PG and UPSC CMS together?', a: 'Yes — the two exams overlap ~70% in syllabus. Most candidates use NEET PG prep as a base and add UPSC-CMS-specific PSM and Surgery depth. Both exams are around 6 months apart, allowing back-to-back attempts in the same year.' },
                            { q: 'Which pays more, NEET PG or UPSC CMS?', a: 'NEET PG leads to clinical specialisation with much higher long-term earnings (₹20L-₹1Cr+ in private practice). UPSC CMS gives a stable ₹80k-₹1.2L government salary from day one with excellent job security and pension benefits.' },
                            { q: 'Is UPSC CMS tougher than NEET PG?', a: 'NEET PG is generally considered harder because of its breadth (19 subjects, 200 Qs in one sitting). UPSC CMS is clinic-focused (240 Qs across 2 papers) and can be covered in 6 months with focused preparation.' },
                        ].map((faq) => (
                            <div key={faq.q} className="rounded-xl border border-border bg-card p-5">
                                <h3 className="font-bold text-sm">{faq.q}</h3>
                                <p className="mt-2 text-sm text-muted-foreground">{faq.a}</p>
                            </div>
                        ))}
                    </div>

                    <div className="mt-12 grid gap-6 sm:grid-cols-2">
                        <Link href="/neet-pg" className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Explore NEET PG</p>
                            <p className="mt-2 font-semibold group-hover:underline">NEET PG Complete Guide <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">Syllabus, pattern, books, cutoff, and preparation strategy for NEET PG 2026.</p>
                        </Link>
                        <Link href="/cms" className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Explore UPSC CMS</p>
                            <p className="mt-2 font-semibold group-hover:underline">UPSC CMS Complete Guide <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">Eligibility, exam pattern, books, salary, cutoff, and 6-month study plan for UPSC CMS 2026.</p>
                        </Link>
                    </div>
                </section>
            </div>
        </>
    );
}
