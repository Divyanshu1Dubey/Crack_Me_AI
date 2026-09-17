import { CMS_VS_NEETPG } from '@/lib/comparisonData';
import ComparisonLayout, { buildComparisonMetadata } from '@/components/ComparisonLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import Script from 'next/script';

export const metadata: Metadata = buildComparisonMetadata(CMS_VS_NEETPG, '/cms/vs-neet-pg');

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'Which is harder, UPSC CMS or NEET PG?', acceptedAnswer: { '@type': 'Answer', text: 'NEET PG is broader (19 subjects, 800 marks, 200 Qs in one go) and considered harder for most candidates. UPSC CMS is clinic-focused (240 Qs across 2 papers) and easier to cover in 6 months.' } },
        { '@type': 'Question', name: 'Can I prepare for UPSC CMS and NEET PG together?', acceptedAnswer: { '@type': 'Answer', text: 'Yes — the two exams overlap ~70% in syllabus. Most candidates use NEET PG prep as a base and add UPSC-CMS-specific PSM and Surgery depth.' } },
        { '@type': 'Question', name: 'Which pays more, UPSC CMS or NEET PG?', acceptedAnswer: { '@type': 'Answer', text: 'NEET PG leads to clinical specialisation with much higher long-term earnings (₹20L-₹1Cr+ private practice). UPSC CMS gives a stable ₹80k-₹1.2L government salary from day one.' } },
    ],
};

export default function CMSVsNEETPGPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'CMS vs NEET PG', path: '/cms/vs-neet-pg' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS vs NEET PG — Which Is Tougher?
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        UPSC CMS and NEET PG are the two biggest postgraduate medical exams in India, but they lead to
                        completely different careers. <strong>NEET PG</strong> gives you an MD/MS seat for clinical practice.
                        <strong> UPSC CMS</strong> gives you a central government Medical Officer post. Here is a detailed
                        side-by-side comparison of pattern, difficulty, salary, and career growth.
                    </p>
                    <div className="mt-8 grid gap-6 sm:grid-cols-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose UPSC CMS if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want a stable central government medical officer post (Railways, CHS, ESIC)</li>
                                <li>You prefer a non-clinical or administrative career path</li>
                                <li>You want to settle early with a gazetted post and job security</li>
                                <li>You do not want to invest 3 years in a residency programme</li>
                            </ul>
                        </div>
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose NEET PG if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want a clinical MD/MS in a specific branch (Medicine, Surgery, Radiology, Anaesthesia)</li>
                                <li>You want to become a superspecialist later (DM/MCh)</li>
                                <li>You are willing to invest 3 years of residency for long-term clinical growth</li>
                                <li>You want private practice or hospital consultant track</li>
                            </ul>
                        </div>
                    </div>
                </section>
                <ComparisonLayout CMS_VS_NEETPG />
            </div>
        </>
    );
}