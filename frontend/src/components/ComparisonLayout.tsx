import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { ArrowRight, CheckCircle2, GraduationCap, Sparkles, Trophy, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import FAQSection from '@/components/FAQSection';

export interface ComparisonRow {
    label: string;
    examA: string;
    examB: string;
    note?: string;
}

export interface ComparisonContent {
    examASlug: 'cms' | 'neet-pg' | 'ini-cet' | 'fmge' | 'usmle';
    examBSlug: 'cms' | 'neet-pg' | 'ini-cet' | 'fmge' | 'usmle';
    examAName: string;
    examBName: string;
    examALandingPath: string;
    examBLandingPath: string;
    /** Bottom-line verdict (1-2 sentences) */
    verdict: string;
    /** SEO description */
    description: string;
    /** "Choose A if …, choose B if …" guidance */
    chooseA: string[];
    chooseB: string[];
    /** Side-by-side comparison rows */
    rows: ComparisonRow[];
    /** FAQs for FAQPage schema */
    faqs: { q: string; a: string }[];
}

export function buildComparisonMetadata(c: ComparisonContent, path: string): Metadata {
    const title = `${c.examAName} vs ${c.examBName} — Which is harder? Comparison | CrackCMS`;
    return {
        title,
        description: c.description,
        alternates: { canonical: path, languages: { 'en-IN': path } },
        openGraph: {
            type: 'article',
            url: path,
            title,
            description: c.description,
            siteName,
            images: [{ url: '/cms-circle-logo.png', width: 1200, height: 630, alt: title }],
        },
        twitter: { card: 'summary_large_image', title, description: c.description },
        robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
    };
}

export default function ComparisonLayout(c: ComparisonContent) {
    const path = `/${c.examASlug}/vs-${c.examBSlug}`;
    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'Article',
                headline: `${c.examAName} vs ${c.examBName} — Comparison`,
                description: c.description,
                inLanguage: 'en-IN',
                datePublished: '2025-01-01',
                dateModified: '2026-07-21',
                author: { '@type': 'Organization', name: siteName, url: siteUrl },
                publisher: { '@type': 'Organization', name: siteName, url: siteUrl },
                mainEntityOfPage: { '@type': 'WebPage', '@id': `${siteUrl}${path}` },
            },
            {
                '@type': 'FAQPage',
                mainEntity: c.faqs.map((f) => ({
                    '@type': 'Question',
                    name: f.q,
                    acceptedAnswer: { '@type': 'Answer', text: f.a },
                })),
            },
            {
                '@type': 'BreadcrumbList',
                itemListElement: [
                    { '@type': 'ListItem', position: 1, name: 'Home', item: `${siteUrl}/` },
                    { '@type': 'ListItem', position: 2, name: c.examAName, item: `${siteUrl}${c.examALandingPath}` },
                    { '@type': 'ListItem', position: 3, name: `vs ${c.examBName}`, item: `${siteUrl}${path}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`vs-${c.examASlug}-${c.examBSlug}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: c.examAName, path: c.examALandingPath }, { name: `vs ${c.examBName}`, path }]} />
                </div>

                <section className="bg-linear-to-br from-indigo-600 to-violet-700 text-white">
                    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
                        <Badge className="bg-white/15 text-white border-white/30 backdrop-blur-sm text-xs font-bold uppercase tracking-wider">
                            <Trophy className="mr-1 inline h-3 w-3" /> Exam comparison
                        </Badge>
                        <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            {c.examAName} vs {c.examBName}
                        </h1>
                        <p className="mt-4 max-w-3xl text-base text-white/85 sm:text-lg">
                            {c.verdict}
                        </p>
                    </div>
                </section>

                {/* Choose cards */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <div className="grid gap-4 md:grid-cols-2">
                        <Card className="border-emerald-500/30 bg-emerald-50/30 dark:bg-emerald-950/20">
                            <CardContent className="p-6">
                                <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">Choose {c.examAName} if…</p>
                                <ul className="mt-4 space-y-2">
                                    {c.chooseA.map((s, i) => (
                                        <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                                <Link href={c.examALandingPath} className="mt-5 inline-flex items-center gap-1 text-sm font-bold text-emerald-700 dark:text-emerald-400 hover:underline">
                                    Read {c.examAName} guide <ArrowRight className="h-4 w-4" />
                                </Link>
                            </CardContent>
                        </Card>
                        <Card className="border-indigo-500/30 bg-indigo-50/30 dark:bg-indigo-950/20">
                            <CardContent className="p-6">
                                <p className="text-xs font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-400">Choose {c.examBName} if…</p>
                                <ul className="mt-4 space-y-2">
                                    {c.chooseB.map((s, i) => (
                                        <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                                <Link href={c.examBLandingPath} className="mt-5 inline-flex items-center gap-1 text-sm font-bold text-indigo-700 dark:text-indigo-400 hover:underline">
                                    Read {c.examBName} guide <ArrowRight className="h-4 w-4" />
                                </Link>
                            </CardContent>
                        </Card>
                    </div>
                </section>

                {/* Comparison table */}
                <section className="mx-auto max-w-5xl px-4 pb-12 sm:px-6">
                    <h2 className="text-2xl font-black tracking-tight sm:text-3xl">Side-by-side comparison</h2>
                    <div className="mt-6 overflow-hidden rounded-2xl border border-border bg-card">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-muted/40">
                                    <th className="px-4 py-3 text-left font-bold text-foreground">Dimension</th>
                                    <th className="px-4 py-3 text-left font-bold text-emerald-700 dark:text-emerald-400">{c.examAName}</th>
                                    <th className="px-4 py-3 text-left font-bold text-indigo-700 dark:text-indigo-400">{c.examBName}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {c.rows.map((r, i) => (
                                    <tr key={i} className="border-t border-border/60">
                                        <td className="px-4 py-3 font-semibold text-foreground align-top">{r.label}</td>
                                        <td className="px-4 py-3 align-top text-foreground">{r.examA}</td>
                                        <td className="px-4 py-3 align-top text-foreground">{r.examB}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* FAQ */}
                <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6">
                    <FAQSection items={c.faqs} title={`${c.examAName} vs ${c.examBName} — FAQs`} />
                </section>

                {/* CTA */}
                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <div className="rounded-3xl border border-primary/30 bg-linear-to-br from-primary/10 via-accent/30 to-teal-500/10 p-8 text-center">
                        <h2 className="text-2xl font-black tracking-tight">Practise both with CrackCMS</h2>
                        <p className="mt-3 text-muted-foreground max-w-xl mx-auto">
                            PYQs from both exams, AI tutor, and exam-mode simulator in one free account.
                        </p>
                        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/register">
                                <Button size="lg" className="gap-2 font-bold">Create free account <ArrowRight className="h-4 w-4" /></Button>
                            </Link>
                        </div>
                    </div>
                </section>
            </div>
        </>
    );
}