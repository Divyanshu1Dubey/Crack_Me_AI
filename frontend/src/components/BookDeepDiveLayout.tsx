import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { ArrowRight, BookOpen, Bookmark, GraduationCap, Lightbulb, Sparkles, Star } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import FAQSection from '@/components/FAQSection';

export interface BookChapter {
    number: number;
    title: string;
    weight: 'high' | 'medium' | 'low';
    note: string;
}

export interface BookDeepDiveContent {
    examSlug: 'cms';
    examName: string;
    examLandingPath: string;
    bookSlug: string;          // e.g. 'harrison'
    bookTitle: string;         // 'Harrison\'s Principles of Internal Medicine'
    bookAuthor: string;        // 'Loscalzo et al.'
    bookEdition?: string;      // '21st'
    /** Subject this book covers */
    subjectName: string;       // 'General Medicine'
    subjectPath: string;       // '/cms/subject/medicine'
    /** 1-2 line verdict */
    verdict: string;
    /** Who should read / who can skip */
    shouldRead: string[];
    canSkip: string[];
    /** High-yield chapters with weight + study note */
    chapters: BookChapter[];
    /** How to read in 30 days — concrete schedule */
    schedule: { week: number; focus: string; pages: string }[];
    /** Pair-with book (companion text) */
    pairWith?: { title: string; why: string };
    faqs: { q: string; a: string }[];
    reviewer: { name: string; credentials: string };
}

export function buildBookDeepDiveMetadata(c: BookDeepDiveContent, path: string): Metadata {
    const title = `${c.bookTitle} for ${c.examName} — Deep-Dive Review, High-Yield Chapters | CrackCMS`;
    const description = `Honest deep-dive review of ${c.bookTitle} for ${c.examName} ${c.subjectName}: high-yield chapters, 30-day reading schedule, FAQs, and verdict from a topper.`;
    return {
        title,
        description,
        alternates: { canonical: path, languages: { 'en-IN': path } },
        openGraph: { type: 'article', url: path, title, description, siteName },
        twitter: { card: 'summary_large_image', title, description },
        robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
    };
}

export default function BookDeepDiveLayout(c: BookDeepDiveContent) {
    const path = `/${c.examSlug}/books/${c.bookSlug}`;
    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'Article',
                headline: `${c.bookTitle} for ${c.examName}`,
                description: `Deep-dive review of ${c.bookTitle} for ${c.examName} ${c.subjectName}.`,
                inLanguage: 'en-IN',
                datePublished: '2025-01-01',
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
                    { '@type': 'ListItem', position: 3, name: 'Books', item: `${siteUrl}/${c.examSlug}/books` },
                    { '@type': 'ListItem', position: 4, name: c.bookTitle, item: `${siteUrl}${path}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`book-${c.examSlug}-${c.bookSlug}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[
                        { name: c.examName, path: c.examLandingPath },
                        { name: 'Books', path: `/${c.examSlug}/books` },
                        { name: c.bookTitle, path },
                    ]} />
                </div>

                <section className="bg-linear-to-br from-indigo-600 to-violet-700 text-white">
                    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
                        <Badge className="bg-white/15 text-white border-white/30 backdrop-blur-sm text-xs font-bold uppercase tracking-wider">
                            <BookOpen className="mr-1 inline h-3 w-3" /> Book deep-dive
                        </Badge>
                        <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            {c.bookTitle}{c.bookEdition ? ` (${c.bookEdition})` : ''}
                        </h1>
                        <p className="mt-2 text-base text-white/80 sm:text-lg">{c.bookAuthor}</p>
                        <p className="mt-4 max-w-3xl text-base text-white/90 sm:text-lg">
                            {c.verdict}
                        </p>
                        <div className="mt-6 flex flex-wrap gap-3">
                            <Link href={c.subjectPath}>
                                <Button size="lg" className="bg-white text-slate-900 hover:bg-white/90 font-bold gap-2 shadow-lg">
                                    Open {c.subjectName} PYQs <ArrowRight className="h-4 w-4" />
                                </Button>
                            </Link>
                        </div>
                    </div>
                </section>

                {/* Should-read / can-skip */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <div className="grid gap-4 md:grid-cols-2">
                        <Card className="border-emerald-500/30 bg-emerald-50/30 dark:bg-emerald-950/20">
                            <CardContent className="p-6">
                                <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">Should read this if…</p>
                                <ul className="mt-4 space-y-2">
                                    {c.shouldRead.map((s, i) => (
                                        <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                                            <Star className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                        <Card className="border-muted/40 bg-muted/20">
                            <CardContent className="p-6">
                                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">You can skip if…</p>
                                <ul className="mt-4 space-y-2">
                                    {c.canSkip.map((s, i) => (
                                        <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                                            <Lightbulb className="mt-0.5 h-4 w-4 shrink-0" />
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    </div>
                </section>

                {/* Chapters */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <Bookmark className="mr-1 inline h-3 w-3" /> High-yield chapters
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">Chapters that matter most</h2>
                    <div className="mt-6 overflow-hidden rounded-2xl border border-border bg-card">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-muted/40">
                                    <th className="px-4 py-3 text-left font-bold">#</th>
                                    <th className="px-4 py-3 text-left font-bold">Chapter</th>
                                    <th className="px-4 py-3 text-left font-bold">Weight</th>
                                    <th className="px-4 py-3 text-left font-bold">Study note</th>
                                </tr>
                            </thead>
                            <tbody>
                                {c.chapters.map((ch) => (
                                    <tr key={ch.number} className="border-t border-border/60">
                                        <td className="px-4 py-3 font-bold">{ch.number}</td>
                                        <td className="px-4 py-3 font-semibold">{ch.title}</td>
                                        <td className="px-4 py-3">
                                            <Badge className={ch.weight === 'high' ? 'bg-emerald-500/15 text-emerald-700 border-emerald-500/30' : ch.weight === 'medium' ? 'bg-amber-500/15 text-amber-700 border-amber-500/30' : 'bg-muted text-muted-foreground'}>
                                                {ch.weight}
                                            </Badge>
                                        </td>
                                        <td className="px-4 py-3 text-muted-foreground">{ch.note}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* 30-day schedule */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <GraduationCap className="mr-1 inline h-3 w-3" /> 30-day reading plan
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">How to read this book in 30 days</h2>
                    <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {c.schedule.map((s) => (
                            <div key={s.week} className="rounded-2xl border border-border bg-card p-5">
                                <p className="text-xs font-bold uppercase tracking-wider text-primary">Week {s.week}</p>
                                <p className="mt-1 text-sm font-bold text-foreground">{s.focus}</p>
                                <p className="mt-1 text-xs text-muted-foreground">{s.pages}</p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Pair with */}
                {c.pairWith && (
                    <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            <Sparkles className="mr-1 inline h-3 w-3" /> Pair with
                        </Badge>
                        <Card className="mt-4 border-primary/30 bg-primary/5">
                            <CardContent className="p-5">
                                <p className="text-base font-bold text-foreground">{c.pairWith.title}</p>
                                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{c.pairWith.why}</p>
                            </CardContent>
                        </Card>
                    </section>
                )}

                {/* FAQ */}
                <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6">
                    <FAQSection items={c.faqs} title={`${c.bookTitle} — FAQs`} />
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <p className="text-center text-xs text-muted-foreground">
                        Reviewed by <span className="font-semibold text-foreground">{c.reviewer.name}</span>, {c.reviewer.credentials}. Last reviewed 21 July 2026.
                    </p>
                </section>
            </div>
        </>
    );
}