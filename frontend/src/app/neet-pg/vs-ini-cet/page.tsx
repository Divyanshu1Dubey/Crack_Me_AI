import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import { ArrowRight } from 'lucide-react';
import Script from 'next/script';

export const metadata: Metadata = {
    title: 'NEET PG vs INI-CET — Which is Better? (2026 Comparison)',
    description: 'NEET PG vs INI-CET: Compare exam pattern, difficulty, negative marking, seats, stipend, institutes (AIIMS vs all India), and which exam suits your career goals.',
    alternates: { canonical: '/neet-pg/vs-ini-cet', languages: { 'en-IN': '/neet-pg/vs-ini-cet' } },
    openGraph: {
        type: 'article',
        url: '/neet-pg/vs-ini-cet',
        title: 'NEET PG vs INI-CET — Which is Better? (2026 Comparison)',
        description: 'NEET PG vs INI-CET: Compare pattern, difficulty, negative marking, seats, stipend, institutes, and career outcomes.',
        siteName,
        images: [{ url: '/cms-circle-logo.png', width: 1200, height: 630, alt: 'NEET PG vs INI-CET' }],
    },
    twitter: { card: 'summary_large_image', title: 'NEET PG vs INI-CET — Which is Better?', description: 'Compare pattern, difficulty, seats, stipend, and career outcomes.' },
    robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'Which is tougher, NEET PG or INI-CET?', acceptedAnswer: { '@type': 'Answer', text: 'INI-CET is generally considered slightly tougher than NEET PG due to deeper clinical reasoning, image-based questions, and tighter negative marking (-1/3 vs no negative marking in NEET PG). However, NEET PG covers a broader syllabus across 19 subjects.' } },
        { '@type': 'Question', name: 'Is INI-CET and NEET PG syllabus same?', acceptedAnswer: { '@type': 'Answer', text: 'Yes — INI-CET and NEET PG share the same core syllabus (19 pre-clinical, para-clinical and clinical subjects). INI-CET questions tend to be more conceptual and image-based, while NEET PG has more memory-based questions.' } },
        { '@type': 'Question', name: 'Can I appear for both NEET PG and INI-CET?', acceptedAnswer: { '@type': 'Answer', text: 'Yes — both exams are conducted by different bodies (NBE for NEET PG, AIIMS for INI-CET). INI-CET is held twice yearly (Jan + July), while NEET PG is once yearly (typically June). Many candidates attempt both to maximise their PG seat options.' } },
    ],
};

export default function NEETPGVsINICETPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'NEET PG', path: '/neet-pg' }, { name: 'NEET PG vs INI-CET', path: '/neet-pg/vs-ini-cet' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        NEET PG vs INI-CET — Which PG Exam is Right for You?
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        NEET PG and INI-CET are the two main postgraduate medical entrance exams in India.
                        <strong> NEET PG</strong> (conducted by NBE) opens MD/MS seats across all medical colleges.
                        <strong> INI-CET</strong> (conducted by AIIMS) opens PG seats at AIIMS, PGIMER, JIPMER, NIMHANS, and SCTIMST.
                        Here is a detailed comparison to help you decide which exam to prioritise.
                    </p>

                    <div className="mt-8 grid gap-6 sm:grid-cols-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose NEET PG if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want MD/MS seats across all medical colleges in India</li>
                                <li>You prefer a broader, more predictable exam pattern</li>
                                <li>You want counselling through MCC (centralised all-India counselling)</li>
                                <li>You are targeting a specific branch (Radiodiagnosis, Dermatology, Orthopaedics)</li>
                            </ul>
                        </div>
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose INI-CET if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want a PG seat at AIIMS, PGI, JIPMER, NIMHANS, SCTIMST</li>
                                <li>You thrive on conceptual, image-based questions</li>
                                <li>You want the prestige and research opportunities of central institutes</li>
                                <li>You can handle the pressure of twice-yearly exams (Jan + July sessions)</li>
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
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">INI-CET</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Conducting body</td><td className="border border-border px-4 py-3">NBE (National Board of Examinations)</td><td className="border border-border px-4 py-3">AIIMS New Delhi (on behalf of INIs)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Frequency</td><td className="border border-border px-4 py-3">Once a year (typically June)</td><td className="border border-border px-4 py-3">Twice a year (January + July)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Questions</td><td className="border border-border px-4 py-3">200 MCQs, single paper</td><td className="border border-border px-4 py-3">200 MCQs, single paper</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Duration</td><td className="border border-border px-4 py-3">3.5 hours (210 min)</td><td className="border border-border px-4 py-3">3 hours (180 min)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Negative marking</td><td className="border border-border px-4 py-3">No</td><td className="border border-border px-4 py-3">Yes (-1/3 per wrong answer)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Total marks</td><td className="border border-border px-4 py-3">800</td><td className="border border-border px-4 py-3">200</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Mode</td><td className="border border-border px-4 py-3">CBT</td><td className="border border-border px-4 py-3">CBT</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Institutes</td><td className="border border-border px-4 py-3">All medical colleges in India (including private)</td><td className="border border-border px-4 py-3">AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST only</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Seats</td><td className="border border-border px-4 py-3">~10,000+ MD/MS seats</td><td className="border border-border px-4 py-3">~1,000-1,500 PG seats</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Difficulty</td><td className="border border-border px-4 py-3">Hard (breadth across 19 subjects)</td><td className="border border-border px-4 py-3">Harder (depth + image-based + -1/3 neg marking)</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Stipend (residency)</td><td className="border border-border px-4 py-3">₹70k-₹1L/month</td><td className="border border-border px-4 py-3">₹90k-₹1.1L/month</td></tr>
                                <tr><td className="border border-border px-4 py-3 font-semibold">Career after PG</td><td className="border border-border px-4 py-3">MD/MS from any college → private practice / faculty / superspecialty</td><td className="border border-border px-4 py-3">MD/MS from AIIMS/PGI → academic + research + private track</td></tr>
                            </tbody>
                        </table>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Key Differences Explained</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">1. Number of attempts and flexibility</h3>
                            <p>NEET PG is held once a year, so you get one shot annually. INI-CET gives you two chances (January and July sessions), which is a significant advantage — if you miss one session, you can try again in six months.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">2. Syllabus and question style</h3>
                            <p>Both exams cover the same 19-subject syllabus, but INI-CET questions are more conceptual and image-based (radiology, pathology slides, dermatology images). NEET PG has a higher proportion of direct, memory-based MCQs. If you are good at visual reasoning, INI-CET may suit you better.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">3. Negative marking impact</h3>
                            <p>INI-CET has -1/3 negative marking, which penalises guessing more than NEET PG (which has no negative marking). This changes your exam strategy — in INI-CET, you should attempt only when reasonably sure. In NEET PG, educated guessing is safer.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">4. Institute brand value</h3>
                            <p>AIIMS, PGI, and JIPMER carry a global brand that opens doors to international fellowships, research positions, and academic careers. NEET PG seats in smaller colleges may not carry the same brand value, but the clinical exposure in peripheral colleges can be excellent.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">5. Preparation strategy</h3>
                            <p>Since the syllabus is ~80% overlapping, most serious candidates prepare for both simultaneously. The recommended approach: use NEET PG prep as your base (standard textbooks + QBank), then add INI-CET-specific image-based practice and conceptual deep-dives 4-6 weeks before the INI-CET session.</p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'Which is tougher, NEET PG or INI-CET?', a: 'INI-CET is generally considered slightly tougher due to deeper clinical reasoning, image-based questions, and -1/3 negative marking. NEET PG is broader but has more memory-based questions and no negative marking, making it slightly more forgiving for average candidates.' },
                            { q: 'Is INI-CET and NEET PG syllabus same?', a: 'Yes — both cover the same 19 pre-clinical, para-clinical and clinical subjects. INI-CET questions tend to be more conceptual and image-based, while NEET PG has a higher proportion of direct recall questions.' },
                            { q: 'Can I appear for both NEET PG and INI-CET?', a: 'Yes — NEET PG is conducted by NBE (once yearly, typically June), while INI-CET is conducted by AIIMS (twice yearly: January and July). Many serious candidates attempt both to maximise their PG seat options across all institutes.' },
                            { q: 'Which institutes are under INI-CET?', a: 'INI-CET is the common entrance exam for: AIIMS (all campuses), PGIMER Chandigarh, JIPMER Puducherry, NIMHANS Bangalore, and SCTIMST Trivandrum. These are Institutes of National Importance with central government funding and high global recognition.' },
                            { q: 'Which is better, NEET PG or INI-CET?', a: 'It depends on your target institute. If you want a PG seat at AIIMS/PGI/JIPMER specifically, INI-CET is your only gateway. If you want the broadest options across all medical colleges in India (including private and state colleges), NEET PG is better. Many top rankers hold both INI-CET and NEET PG ranks and choose based on branch and institute.' },
                        ].map((faq) => (
                            <div key={faq.q} className="rounded-xl border border-border bg-card p-5">
                                <h3 className="font-bold text-sm">{faq.q}</h3>
                                <p className="mt-2 text-sm text-muted-foreground">{faq.a}</p>
                            </div>
                        ))}
                    </div>

                    <div className="mt-12 grid gap-6 sm:grid-cols-2">
                        <Link href="/neet-pg" className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold uppercase tracking-wider text-muted-foreground">NEET PG</p>
                            <p className="mt-2 font-semibold group-hover:underline">NEET PG Preparation <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">2,300+ PYQs, AI tutor, mock tests, and a complete NEET PG landing page.</p>
                        </Link>
                        <Link href="/ini-cet" className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-sm font-bold uppercase tracking-wider text-muted-foreground">INI-CET</p>
                            <p className="mt-2 font-semibold group-hover:underline">INI-CET Preparation <ArrowRight className="inline ml-1 h-4 w-4" /></p>
                            <p className="mt-1 text-sm text-muted-foreground">12,000+ PYQs for AIIMS, PGI, JIPMER, NIMHANS. AI tutor, CBT mocks, rank predictor.</p>
                        </Link>
                    </div>
                </section>
            </div>
        </>
    );
}
