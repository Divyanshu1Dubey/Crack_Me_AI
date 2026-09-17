import { NEETPG_VS_USMLE } from '@/lib/comparisonData';
import ComparisonLayout, { buildComparisonMetadata } from '@/components/ComparisonLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import Script from 'next/script';

export const metadata: Metadata = buildComparisonMetadata(NEETPG_VS_USMLE, '/neet-pg/vs-usmle');

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'Is USMLE harder than NEET PG?', acceptedAnswer: { '@type': 'Answer', text: 'USMLE Step 1 is conceptually deeper and tests applied reasoning, not memorisation. The pass rate for IMGs is ~80% on Step 1, but matching into residency is harder (~50% match rate for IMGs). NEET PG is broader and more memory-heavy.' } },
        { '@type': 'Question', name: 'Should Indian MBBS students attempt USMLE?', acceptedAnswer: { '@type': 'Answer', text: 'If you can afford ₹15-25L in prep + application costs, have a Step 1 score of 240+, and want global clinical exposure, USMLE is worth it. Otherwise, NEET PG remains the practical choice for most Indian graduates.' } },
        { '@type': 'Question', name: 'Can I prepare for USMLE and NEET PG together?', acceptedAnswer: { '@type': 'Answer', text: 'Yes — pre-clinical and clinical subjects overlap heavily. Many Indian aspirants use First Aid + UWorld for USMLE while solving NEET PG MCQs alongside.' } },
    ],
};

export default function NEETPGVsUSMLEPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'NEET PG', path: '/neet-pg' }, { name: 'NEET PG vs USMLE', path: '/neet-pg/vs-usmle' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        NEET PG vs USMLE — Which is Better for Indian MBBS Doctors?
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        NEET PG and USMLE are the two main postgraduate medical entrance routes for Indian MBBS graduates,
                        but they lead to completely different careers. <strong>NEET PG</strong> gives you an MD/MS seat in India
                        (₹2-15L total cost, 12-18 months prep). <strong>USMLE Step 1</strong> opens the door to US residency
                        (₹15-25L total cost, 18-30 months prep, with the option to skip Step 2 CK and match separately).
                        Here is a detailed comparison to help you decide.
                    </p>
                    <div className="mt-8 grid gap-6 sm:grid-cols-2">
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose NEET PG if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want to specialise and practise in India</li>
                                <li>You have financial constraints (USMLE prep + applications are expensive)</li>
                                <li>You want a faster path to PG (12-18 months vs 18-30 months)</li>
                                <li>You want to be close to family and avoid the US match lottery</li>
                            </ul>
                        </div>
                        <div className="rounded-2xl border border-border bg-card p-6">
                            <h3 className="text-lg font-bold">Choose USMLE if…</h3>
                            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <li>You want to practise in the US or do global research</li>
                                <li>You can afford ₹15-25L in prep + application costs</li>
                                <li>You have a strong academic foundation (target Step 1 score 240+)</li>
                                <li>You want exposure to world-class clinical training and research</li>
                            </ul>
                        </div>
                    </div>
                </section>
                <ComparisonLayout NEETPG_VS_USMLE />
            </div>
        </>
    );
}