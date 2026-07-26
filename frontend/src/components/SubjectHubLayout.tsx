import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import {
    ArrowRight, BookOpen, Brain, CheckCircle2, ChevronRight,
    GraduationCap, Sparkles, Target, Trophy
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import FAQSection from '@/components/FAQSection';

export interface SubjectHubContent {
    examSlug: 'cms' | 'neet-pg' | 'ini-cet' | 'fmge' | 'usmle';
    examName: string;
    examLandingPath: string;
    subjectSlug: string;        // e.g. 'medicine'
    subjectName: string;        // e.g. 'General Medicine'
    subjectShort: string;       // e.g. 'Medicine'
    /** Estimated questions in this subject across all years */
    questionCount: number;
    /** Approximate weightage percentage (0-100) */
    weightagePct: number;
    /** Books recommended for this subject */
    books: { title: string; author: string; edition?: string; why: string }[];
    /** High-yield topics */
    highYieldTopics: { name: string; frequency: 'every-year' | 'often' | 'sometimes' }[];
    /** Mnemonic the platform teaches for this subject */
    topMnemonic?: { title: string; body: string };
    /** Year-wise frequency buckets */
    yearWise: { year: number; count: number }[];
    /** FAQs for FAQ schema */
    faqs: { q: string; a: string }[];
    /** Reviewed-by byline */
    reviewer: { name: string; credentials: string };
}

const ACCENT: Record<SubjectHubContent['examSlug'], { from: string; to: string }> = {
    cms: { from: 'from-indigo-600', to: 'to-violet-700' },
    'neet-pg': { from: 'from-emerald-600', to: 'to-teal-700' },
    'ini-cet': { from: 'from-pink-600', to: 'to-rose-700' },
    fmge: { from: 'from-amber-600', to: 'to-orange-700' },
    usmle: { from: 'from-purple-600', to: 'to-indigo-700' },
};

export function buildSubjectHubMetadata(c: SubjectHubContent): Metadata {
    const path = `/${c.examSlug}/subject/${c.subjectSlug}`;
    const title = `${c.examName} ${c.subjectName} — PYQs, High-Yield Topics, Books | CrackCMS`;
    const description = `Master ${c.subjectName} for ${c.examName}. Practice ${c.questionCount}+ ${c.subjectName} PYQs, learn high-yield topics, see year-wise question distribution and book recommendations.`;
    return {
        title,
        description,
        alternates: { canonical: path, languages: { 'en-IN': path } },
        openGraph: {
            type: 'article',
            url: path,
            title,
            description,
            siteName,
            images: [{ url: '/cms-circle-logo.png', width: 1200, height: 630, alt: title }],
        },
        twitter: { card: 'summary_large_image', title, description },
        robots: {
            index: true,
            follow: true,
            googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 },
        },
    };
}

export default function SubjectHubLayout(c: SubjectHubContent) {
    const path = `/${c.examSlug}/subject/${c.subjectSlug}`;
    const accent = ACCENT[c.examSlug];
    const breadcrumbItems = [
        { name: c.examName, path: c.examLandingPath },
        { name: 'Subjects', path: `/${c.examSlug}/subject` },
        { name: c.subjectShort, path },
    ];

    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'MedicalWebPage',
                headline: `${c.examName} ${c.subjectName} — PYQs, High-Yield Topics, Books`,
                description: `Comprehensive ${c.subjectName} PYQ practice, topic-wise high-yield analysis, and book recommendations for ${c.examName}.`,
                inLanguage: 'en-IN',
                datePublished: '2024-08-01',
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
                    { '@type': 'ListItem', position: 3, name: 'Subjects', item: `${siteUrl}/${c.examSlug}/subject` },
                    { '@type': 'ListItem', position: 4, name: c.subjectShort, item: `${siteUrl}${path}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`subject-hub-${c.examSlug}-${c.subjectSlug}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-6xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={breadcrumbItems} />
                </div>

                {/* Hero */}
                <section className={`bg-linear-to-br ${accent.from} ${accent.to} text-white`}>
                    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
                        <Badge className="bg-white/15 text-white border-white/30 backdrop-blur-sm text-xs font-bold uppercase tracking-wider">
                            <GraduationCap className="mr-1 inline h-3 w-3" /> {c.examName} Subject Hub
                        </Badge>
                        <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            {c.examName} {c.subjectName} PYQs & High-Yield Topics
                        </h1>
                        <p className="mt-4 max-w-3xl text-base text-white/85 sm:text-lg">
                            Master {c.subjectShort} with {c.questionCount}+ previous-year questions, year-wise
                            frequency analysis, top books, and AI-powered explanations grounded in standard
                            references.
                        </p>
                        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                            {[
                                { number: `${c.questionCount}+`, label: `${c.subjectShort} PYQs` },
                                { number: `${c.weightagePct}%`, label: 'Exam weightage' },
                                { number: `${c.highYieldTopics.length}`, label: 'High-yield topics' },
                                { number: `${c.books.length}`, label: 'Top books' },
                            ].map((s) => (
                                <div key={s.label} className="rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 p-4 shadow-xl">
                                    <p className="text-xl font-black text-white sm:text-2xl">{s.number}</p>
                                    <p className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-white/80">{s.label}</p>
                                </div>
                            ))}
                        </div>
                        <div className="mt-6 flex flex-wrap gap-3">
                            <Link href="/register">
                                <Button size="lg" className="bg-white text-slate-900 hover:bg-white/90 font-bold gap-2 shadow-lg">
                                    Start Practising <ArrowRight className="h-4 w-4" />
                                </Button>
                            </Link>
                            <Link href={`/questions?exam=${c.examSlug.toUpperCase()}&subject=${c.subjectSlug}`}>
                                <Button size="lg" variant="outline" className="border-white/40 bg-white/10 text-white hover:bg-white/20 backdrop-blur-sm font-bold gap-2">
                                    <BookOpen className="h-4 w-4" /> Open Question Bank
                                </Button>
                            </Link>
                        </div>
                    </div>
                </section>

                {/* Year-wise frequency */}
                <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <Target className="mr-1 inline h-3 w-3" /> Year-wise Frequency
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                        How {c.subjectShort} questions are distributed across recent {c.examName} years
                    </h2>
                    <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        {c.yearWise.map((y) => (
                            <div key={y.year} className="rounded-2xl border border-border bg-card p-5 text-center">
                                <p className="text-3xl font-black text-foreground">{y.count}</p>
                                <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{y.year}</p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* High-yield topics */}
                <section className="border-y border-border bg-muted/30">
                    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            <Sparkles className="mr-1 inline h-3 w-3" /> High-yield topics
                        </Badge>
                        <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                            Most-tested {c.subjectShort} topics in {c.examName}
                        </h2>
                        <ul className="mt-6 space-y-3">
                            {c.highYieldTopics.map((t) => (
                                <li key={t.name} className="flex items-start gap-3 rounded-2xl border border-border bg-card p-4">
                                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                                    <div className="flex-1">
                                        <p className="text-sm font-bold text-foreground">{t.name}</p>
                                        <p className="mt-0.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                            Frequency: {t.frequency === 'every-year' ? 'Every year' : t.frequency === 'often' ? 'Often' : 'Sometimes'}
                                        </p>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </div>
                </section>

                {/* Books */}
                <section className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <BookOpen className="mr-1 inline h-3 w-3" /> Recommended books
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                        Best books for {c.subjectShort} in {c.examName}
                    </h2>
                    <div className="mt-6 grid gap-4 md:grid-cols-2">
                        {c.books.map((b) => (
                            <Card key={b.title} className="border-border/60 bg-card">
                                <CardContent className="p-5">
                                    <p className="text-base font-bold text-foreground">{b.title}</p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {b.author}{b.edition ? ` · ${b.edition}` : ''}
                                    </p>
                                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{b.why}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </section>

                {/* Top mnemonic */}
                {c.topMnemonic && (
                    <section className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
                        <Badge className="bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30 text-xs font-bold uppercase tracking-wider">
                            <Brain className="mr-1 inline h-3 w-3" /> Top memory trick
                        </Badge>
                        <Card className="mt-4 border-amber-500/30 bg-amber-50/30 dark:bg-amber-950/20">
                            <CardContent className="p-5">
                                <h3 className="text-base font-bold text-foreground">{c.topMnemonic.title}</h3>
                                <p className="mt-2 text-sm leading-relaxed text-foreground">{c.topMnemonic.body}</p>
                            </CardContent>
                        </Card>
                    </section>
                )}

                {/* FAQ */}
                <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6">
                    <FAQSection items={c.faqs} title={`${c.examName} ${c.subjectShort} — FAQs`} />
                </section>

                {/* CTA + reviewer */}
                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <div className="rounded-3xl border border-primary/30 bg-linear-to-br from-primary/10 via-accent/30 to-teal-500/10 p-8 sm:p-12 text-center">
                        <h2 className="text-2xl font-black tracking-tight sm:text-3xl">
                            Practise {c.subjectShort} PYQs now
                        </h2>
                        <p className="mt-3 text-muted-foreground max-w-xl mx-auto">
                            Join thousands of medical aspirants using CrackCMS to prepare smarter. Start free today.
                        </p>
                        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/register">
                                <Button size="lg" className="gap-2 font-bold">
                                    Create free account <ArrowRight className="h-4 w-4" />
                                </Button>
                            </Link>
                            <Link href={`/questions?exam=${c.examSlug.toUpperCase()}&subject=${c.subjectSlug}`}>
                                <Button size="lg" variant="outline" className="gap-2 font-bold">
                                    Open Question Bank
                                </Button>
                            </Link>
                        </div>
                    </div>
                    <p className="mt-6 text-center text-xs text-muted-foreground">
                        Medically reviewed by <span className="font-semibold text-foreground">{c.reviewer.name}</span>, {c.reviewer.credentials}. Last reviewed 21 July 2026.
                    </p>
                </section>
            </div>
        </>
    );
}