import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { ArrowRight, Calendar, Target, TrendingUp, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import FAQSection from '@/components/FAQSection';

export interface CutoffContent {
    examSlug: 'cms' | 'neet-pg';
    examName: string;
    examLandingPath: string;
    year: number;
    /** Total candidates appeared (approx) */
    candidatesAppeared?: number;
    /** Total candidates recommended (approx) */
    candidatesRecommended?: number;
    /** Category-wise cutoff out of 960 (CMS) or 800 (NEET PG) */
    cutoffs: { category: string; cutoff: number; seats?: number }[];
    /** Top 5 topper scores */
    toppers: { rank: number; name: string; score: string }[];
    /** Year-over-year trend */
    trend: { category: string; prevYear: number; thisYear: number }[];
    faqs: { q: string; a: string }[];
    reviewer: { name: string; credentials: string };
}

export function buildCutoffMetadata(c: CutoffContent, path: string): Metadata {
    const title = `${c.examName} ${c.year} Cutoff Marks — Category-wise Qualifying Marks | CrackCMS`;
    const description = `Category-wise ${c.examName} ${c.year} cutoff marks, topper scores, year-over-year trends, and FAQs. See if you would have qualified.`;
    return {
        title,
        description,
        alternates: { canonical: path, languages: { 'en-IN': path } },
        openGraph: { type: 'article', url: path, title, description, siteName },
        twitter: { card: 'summary_large_image', title, description },
        robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
    };
}

export default function CutoffLayout(c: CutoffContent) {
    const path = `/${c.examSlug}/cutoff/${c.year}`;
    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'Article',
                headline: `${c.examName} ${c.year} Cutoff Marks`,
                description: `Category-wise ${c.examName} ${c.year} cutoff, topper scores, and year-over-year trends.`,
                inLanguage: 'en-IN',
                datePublished: `${c.year}-09-01`,
                dateModified: '2026-07-21',
                author: { '@type': 'Organization', name: siteName, url: siteUrl },
                publisher: { '@type': 'Organization', name: siteName, url: siteUrl },
                reviewedBy: { '@type': 'Person', name: c.reviewer.name, credentials: c.reviewer.credentials },
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
                    { '@type': 'ListItem', position: 2, name: c.examName, item: `${siteUrl}${c.examLandingPath}` },
                    { '@type': 'ListItem', position: 3, name: 'Cutoff', item: `${siteUrl}/${c.examSlug}/cutoff` },
                    { '@type': 'ListItem', position: 4, name: String(c.year), item: `${siteUrl}${path}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`cutoff-${c.examSlug}-${c.year}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[
                        { name: c.examName, path: c.examLandingPath },
                        { name: 'Cutoff', path: `/${c.examSlug}/cutoff` },
                        { name: String(c.year), path },
                    ]} />
                </div>

                <section className="bg-gradient-to-br from-indigo-600 to-violet-700 text-white">
                    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
                        <Badge className="bg-white/15 text-white border-white/30 backdrop-blur-sm text-xs font-bold uppercase tracking-wider">
                            <Calendar className="mr-1 inline h-3 w-3" /> {c.examName} {c.year}
                        </Badge>
                        <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            {c.examName} {c.year} Cutoff Marks — Category-wise
                        </h1>
                        <p className="mt-4 max-w-3xl text-base text-white/85 sm:text-lg">
                            Category-wise qualifying marks for {c.examName} {c.year}, topper scores, and
                            year-over-year cutoff trend analysis.
                        </p>
                    </div>
                </section>

                {/* Cutoff table */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <Target className="mr-1 inline h-3 w-3" /> Category-wise Cutoff
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">Qualifying marks by category</h2>
                    <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        {c.cutoffs.map((row) => (
                            <div key={row.category} className="rounded-2xl border border-border bg-card p-5 text-center">
                                <p className="text-3xl font-black text-foreground">{row.cutoff}</p>
                                <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{row.category}</p>
                                {typeof row.seats === 'number' && (
                                    <p className="mt-1 text-[10px] text-muted-foreground">{row.seats} seats</p>
                                )}
                            </div>
                        ))}
                    </div>
                </section>

                {/* Toppers */}
                {c.toppers.length > 0 && (
                    <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            <Trophy className="mr-1 inline h-3 w-3" /> {c.year} Toppers
                        </Badge>
                        <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">Top rankers in {c.examName} {c.year}</h2>
                        <div className="mt-6 grid gap-3 sm:grid-cols-2">
                            {c.toppers.map((t) => (
                                <div key={t.rank} className="rounded-2xl border border-border bg-card p-5">
                                    <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">AIR {t.rank}</p>
                                    <p className="mt-1 text-sm font-bold text-foreground">{t.name}</p>
                                    <p className="mt-1 text-xs font-semibold text-primary">Score: {t.score}</p>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Trend */}
                {c.trend.length > 0 && (
                    <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            <TrendingUp className="mr-1 inline h-3 w-3" /> Cutoff trend
                        </Badge>
                        <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                            How {c.year} compares to last year
                        </h2>
                        <div className="mt-6 overflow-hidden rounded-2xl border border-border bg-card">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="bg-muted/40">
                                        <th className="px-4 py-3 text-left font-bold">Category</th>
                                        <th className="px-4 py-3 text-left font-bold">{c.year - 1}</th>
                                        <th className="px-4 py-3 text-left font-bold">{c.year}</th>
                                        <th className="px-4 py-3 text-left font-bold">Change</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {c.trend.map((t) => {
                                        const change = t.thisYear - t.prevYear;
                                        const changeStr = change > 0 ? `+${change}` : `${change}`;
                                        return (
                                            <tr key={t.category} className="border-t border-border/60">
                                                <td className="px-4 py-3 font-semibold">{t.category}</td>
                                                <td className="px-4 py-3">{t.prevYear}</td>
                                                <td className="px-4 py-3">{t.thisYear}</td>
                                                <td className={`px-4 py-3 font-bold ${change > 0 ? 'text-emerald-600' : change < 0 ? 'text-red-500' : 'text-muted-foreground'}`}>
                                                    {changeStr}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {/* FAQ */}
                <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6">
                    <FAQSection items={c.faqs} title={`${c.examName} ${c.year} Cutoff — FAQs`} />
                </section>

                {/* CTA */}
                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <div className="rounded-3xl border border-primary/30 bg-gradient-to-br from-primary/10 via-accent/30 to-teal-500/10 p-8 text-center">
                        <h2 className="text-2xl font-black tracking-tight">Practise {c.examName} PYQs</h2>
                        <p className="mt-3 text-muted-foreground max-w-xl mx-auto">
                            See what score you can hit. Free tier includes practice, AI explanations, and analytics.
                        </p>
                        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/register">
                                <Button size="lg" className="gap-2 font-bold">Create free account <ArrowRight className="h-4 w-4" /></Button>
                            </Link>
                            <Link href={`/questions?exam=${c.examSlug.toUpperCase()}`}>
                                <Button size="lg" variant="outline" className="gap-2 font-bold">Open Question Bank</Button>
                            </Link>
                        </div>
                    </div>
                    <p className="mt-6 text-center text-xs text-muted-foreground">
                        Source: UPSC official press release / result PDF. Reviewed by <span className="font-semibold text-foreground">{c.reviewer.name}</span>, {c.reviewer.credentials}.
                    </p>
                </section>
            </div>
        </>
    );
}