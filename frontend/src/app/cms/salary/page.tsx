import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import Script from 'next/script';

const title = 'UPSC CMS Salary 2026 — Pay, Allowances, Career Growth & Promotion';
const description = 'Complete UPSC CMS salary structure for 2026: basic pay, NPA, HRA, DA, promotion hierarchy (MO → ADMO → CMO → DGHS), and in-hand salary breakdown for General Duty Medical Officers.';
const slug = 'cms-salary';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        {
            '@type': 'Question',
            name: 'What is the salary of a UPSC CMS Medical Officer in 2026?',
            acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS recruits Medical Officers at Pay Level 10 (7th CPC) with basic pay ₹56,100 - ₹1,77,500. With 20% NPA, DA, HRA, and other allowances, the approximate in-hand salary is ₹80,000 - ₹1,20,000 per month for newly recruited GDMOs.' },
        },
        {
            '@type': 'Question',
            name: 'Does UPSC CMS officer get Non-Practising Allowance?',
            acceptedAnswer: { '@type': 'Answer', text: 'Yes — Medical Officers appointed through UPSC CMS receive 20% Non-Practising Allowance (NPA) on basic pay, provided they do not run private practice. This is a significant benefit over many other central government jobs.' },
        },
        {
            '@type': 'Question',
            name: 'What is the career growth after UPSC CMS?',
            acceptedAnswer: { '@type': 'Answer', text: 'The promotion hierarchy is: Medical Officer (MO) → Senior Medical Officer (SMO) → Assistant Divisional Medical Officer (ADMO) → Chief Medical Officer (CMO) → Additional Director → Director → DGHS. Typical time to first promotion: 4-5 years.' },
        },
    ],
};

export default function CMSSalaryPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Salary & Career', path: '/cms/salary' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Salary 2026 — Complete Pay, Allowances &amp; Career Growth
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        UPSC CMS recruits Medical Officers, Specialists, and Assistant Divisional Medical Officers
                        under the 7th Pay Commission. Here is the complete salary breakdown, allowance structure,
                        promotion hierarchy, and in-hand pay for 2026.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <h2 className="text-2xl font-bold mb-4">UPSC CMS Salary Structure (7th Pay Commission)</h2>
                    <p className="text-muted-foreground mb-6">
                        UPSC CMS officers are placed under <strong>Pay Level 10</strong> of the 7th Central Pay Commission.
                        The starting basic pay and grade pay have been subsumed into a consolidated pay matrix.
                    </p>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse rounded-xl border border-border overflow-hidden">
                            <thead>
                                <tr className="bg-muted">
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Post</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Pay Level</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Basic Pay (₹)</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">In-Hand Est. (₹/month)</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className="border border-border px-4 py-3">Medical Officer (GDMO)</td><td className="border border-border px-4 py-3">Level 10</td><td className="border border-border px-4 py-3">₹56,100</td><td className="border border-border px-4 py-3">₹80,000 – ₹95,000</td></tr>
                                <tr><td className="border border-border px-4 py-3">Senior Medical Officer</td><td className="border border-border px-4 py-3">Level 11</td><td className="border border-border px-4 py-3">₹67,700</td><td className="border border-border px-4 py-3">₹95,000 – ₹1,10,000</td></tr>
                                <tr><td className="border border-border px-4 py-3">ADMO / Specialist</td><td className="border border-border px-4 py-3">Level 12</td><td className="border border-border px-4 py-3">₹78,800</td><td className="border border-border px-4 py-3">₹1,10,000 – ₹1,35,000</td></tr>
                                <tr><td className="border border-border px-4 py-3">Chief Medical Officer</td><td className="border border-border px-4 py-3">Level 13</td><td className="border border-border px-4 py-3">₹1,23,100</td><td className="border border-border px-4 py-3">₹1,55,000 – ₹1,80,000</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-4 text-xs text-muted-foreground">
                        * In-hand estimates include basic pay + 20% NPA + 46% DA (as of 2026) + HRA (if not in government quarters) + other allowances. Actual figures vary by posting city and department.
                    </p>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Allowances &amp; Benefits</h2>
                    <ul className="space-y-3 text-muted-foreground">
                        <li><strong>Non-Practising Allowance (NPA):</strong> 20% of basic pay for doctors not running private practice.</li>
                        <li><strong>Dearness Allowance (DA):</strong> Currently ~46% of basic pay, revised every 6 months.</li>
                        <li><strong>House Rent Allowance (HRA):</strong> 24-30% of basic pay depending on city classification (X/Y/Z).</li>
                        <li><strong>Transport Allowance (TA):</strong> ₹3,600 - ₹7,200 per month depending on grade.</li>
                        <li><strong>Medical facilities:</strong> Free medical care for self and dependents at government hospitals.</li>
                        <li><strong>Leave Travel Concession (LTC):</strong> Once every 2 years for home town / all-India tour.</li>
                        <li><strong>Pension:</strong> As per NPS or old pension scheme (depending on joining date).</li>
                        <li><strong>Rural / Remote area allowance:</strong> Additional ₹1,000-₹2,000/month for postings in difficult areas.</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Promotion Hierarchy &amp; Career Growth</h2>
                    <p className="text-muted-foreground mb-6">
                        UPSC CMS offers a clear career progression path for medical officers. Typical time to each promotion
                        depends on department vacancies and performance, but the general timeline is:
                    </p>
                    <div className="space-y-4">
                        {[
                            { rank: 'Medical Officer (MO)', time: 'Joining', level: 'Level 10' },
                            { rank: 'Senior Medical Officer (SMO)', time: '4-5 years', level: 'Level 11' },
                            { rank: 'Assistant Divisional Medical Officer (ADMO)', time: '8-12 years', level: 'Level 12' },
                            { rank: 'Chief Medical Officer (CMO)', time: '15-20 years', level: 'Level 13-14' },
                            { rank: 'Additional Director / Director', time: '22-28 years', level: 'Level 14-15' },
                            { rank: 'Director General of Health Services (DGHS)', time: '28+ years', level: 'Level 17 (HAG+)' },
                        ].map((step) => (
                            <div key={step.rank} className="flex items-center gap-4 rounded-xl border border-border bg-card p-4">
                                <div className="flex-1">
                                    <p className="font-bold">{step.rank}</p>
                                    <p className="text-sm text-muted-foreground">{step.level}</p>
                                </div>
                                <p className="text-sm font-semibold text-primary">{step.time}</p>
                            </div>
                        ))}
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Salary Comparison: UPSC CMS vs NEET PG vs INI-CET</h2>
                    <p className="text-muted-foreground mb-6">
                        While NEET PG and INI-CET lead to MD/MS degrees (not immediate salaries), here is how the
                        long-term earnings compare:
                    </p>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse rounded-xl border border-border overflow-hidden">
                            <thead>
                                <tr className="bg-muted">
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Career Path</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Starting Monthly</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Peak Monthly</th>
                                    <th className="border border-border px-4 py-3 text-left text-sm font-bold">Job Security</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td className="border border-border px-4 py-3">UPSC CMS (MO)</td><td className="border border-border px-4 py-3">₹80k-₹95k</td><td className="border border-border px-4 py-3">₹1.5L-₹2L</td><td className="border border-border px-4 py-3">Very High</td></tr>
                                <tr><td className="border border-border px-4 py-3">NEET PG (MD/MS resident)</td><td className="border border-border px-4 py-3">₹70k-₹1L stipend</td><td className="border border-border px-4 py-3">₹5L-₹50L+ private</td><td className="border border-border px-4 py-3">Low (residency) → High after</td></tr>
                                <tr><td className="border border-border px-4 py-3">INI-CET (MD/MS at AIIMS)</td><td className="border border-border px-4 py-3">₹90k-₹1.1L stipend</td><td className="border border-border px-4 py-3">₹3L-₹30L+ (academic + private)</td><td className="border border-border px-4 py-3">High (AIIMS/PGI tag)</td></tr>
                            </tbody>
                        </table>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'Is UPSC CMS salary better than NEET PG?', a: 'UPSC CMS gives you a stable ₹80k-₹1.2L government salary from day one with job security. NEET PG residents earn a stipend of ₹70k-₹1L during 3-year residency, but long-term earnings as a specialist (MD/MS) are much higher — ₹20L-₹1Cr+ in private practice. UPSC CMS is better for stability; NEET PG is better for long-term earning potential.' },
                            { q: 'Does UPSC CMS salary increase after retirement?', a: 'UPSC CMS officers receive a pension under the National Pension System (NPS) or old pension scheme (depending on joining date). The pension is typically 50% of the last drawn basic pay. After retirement, many CMOs take up private practice or consulting roles, adding significantly to income.' },
                            { q: 'What is the salary of an ADMO through UPSC CMS?', a: 'An Assistant Divisional Medical Officer (ADMO) is placed at Pay Level 12 with basic pay ₹78,800. With allowances, the in-hand salary is approximately ₹1,10,000 - ₹1,35,000 per month.' },
                            { q: 'Do UPSC CMS officers get government quarters?', a: 'Yes — most central government departments provide accommodation or HRA in lieu. Railways, CHS, and ESIC typically have staff quarters at major postings. If accommodation is not provided, HRA (24-30% of basic) is paid.' },
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
