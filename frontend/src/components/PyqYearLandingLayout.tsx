import type { Metadata } from 'next';
import Link from 'next/link';
import { TrackedLink } from '@/components/TrackedLink';
import Script from 'next/script';
import { CheckCircle2, ArrowRight, BarChart3, BookOpen, Calendar, Target, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import FAQSection from '@/components/FAQSection';

export interface PyqYearContent {
    examSlug: 'cms' | 'neet-pg' | 'ini-cet' | 'fmge' | 'usmle';
    examName: string; // 'UPSC CMS'
    year: number;
    totalQuestions: number;
    totalSubjects: number;
    topSubjects: { name: string; count: number }[];
    cutoffGeneral?: number;
    cutoffObc?: number;
    cutoffSc?: number;
    cutoffSt?: number;
    cutoffPwD?: number;
    toppers?: { name: string; score: string }[];
    keyTrends: string[]; // 4-6 unique high-yield observations about this specific year
    faqs: { q: string; a: string }[];
    examLandingPath: string; // '/cms' for canonical linking
}

const ACCENT: Record<PyqYearContent['examSlug'], { from: string; to: string }> = {
    cms: { from: 'from-indigo-600', to: 'to-violet-700' },
    'neet-pg': { from: 'from-emerald-600', to: 'to-teal-700' },
    'ini-cet': { from: 'from-pink-600', to: 'to-rose-700' },
    fmge: { from: 'from-amber-600', to: 'to-orange-700' },
    usmle: { from: 'from-purple-600', to: 'to-indigo-700' },
};

export function buildPyqYearMetadata(c: PyqYearContent): Metadata {
    const path = `/${c.examSlug}/pyq/${c.year}`;
    const title = `${c.examName} ${c.year} Previous Year Questions — PYQs, Cutoff, Toppers | CrackCMS`;
    const description = `Practice ${c.totalQuestions}+ ${c.examName} ${c.year} previous-year questions. Subject-wise PYQs, ${c.year} cutoff, topper scores, and AI explanations grounded in standard textbooks.`;
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

export default function PyqYearLandingLayout(c: PyqYearContent) {
    const path = `/${c.examSlug}/pyq/${c.year}`;
    const accent = ACCENT[c.examSlug];
    const breadcrumbItems = [
        { name: c.examName, path: c.examLandingPath },
        { name: 'PYQs', path: `/${c.examSlug}/pyq` },
        { name: String(c.year), path },
    ];

    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'Article',
                headline: `${c.examName} ${c.year} Previous Year Questions`,
                description: `Comprehensive ${c.examName} ${c.year} PYQ practice with subject-wise breakdown, ${c.year} cutoff, toppers, and AI explanations.`,
                inLanguage: 'en-IN',
                datePublished: `${c.year}-08-01`,
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
                    { '@type': 'ListItem', position: 2, name: c.examName, item: `${siteUrl}${c.examLandingPath}` },
                    { '@type': 'ListItem', position: 3, name: 'PYQs', item: `${siteUrl}/${c.examSlug}/pyq` },
                    { '@type': 'ListItem', position: 4, name: String(c.year), item: `${siteUrl}${path}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`pyq-year-${c.examSlug}-${c.year}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-6xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={breadcrumbItems} />
                </div>

                <section className={`bg-linear-to-br ${accent.from} ${accent.to} text-white`}>
                    <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-2">
                        <div>
                            <Badge className="bg-white/15 text-white border-white/30 backdrop-blur-sm text-xs font-bold uppercase tracking-wider">
                                <Calendar className="mr-1 inline h-3 w-3" /> {c.examName} {c.year}
                            </Badge>
                            <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                                {c.examName} {c.year} PYQs — Full Paper, Subject-wise & AI Explanations
                            </h1>
                            <p className="mt-4 max-w-2xl text-base text-white/85 sm:text-lg">
                                Practice {c.totalQuestions}+ verified previous-year questions from {c.examName} {c.year}.
                                Filter by subject, difficulty, and topic. Get AI-powered explanations grounded in
                                Harrison, Bailey & Love, Ghai, Park and other standard references.
                            </p>
                            <div className="mt-6 flex flex-wrap gap-3">
                                <Link href="/register">
                                    <Button size="lg" className="bg-white text-slate-900 hover:bg-white/90 font-bold gap-2 shadow-lg">
                                        Start Practising <ArrowRight className="h-4 w-4" />
                                    </Button>
                                </Link>
                                <Link href={`/questions?exam=${c.examSlug.toUpperCase()}&year=${c.year}`}>
                                    <Button size="lg" variant="outline" className="border-white/40 bg-white/10 text-white hover:bg-white/20 backdrop-blur-sm font-bold gap-2">
                                        <BookOpen className="h-4 w-4" /> Open PYQ Bank
                                    </Button>
                                </Link>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 self-center">
                            {[
                                { number: `${c.totalQuestions}+`, label: `${c.year} PYQs` },
                                { number: String(c.totalSubjects), label: 'Subjects covered' },
                                { number: 'AI tutor', label: 'Every answer' },
                                { number: 'Free tier', label: 'Practice today' },
                            ].map((s) => (
                                <div key={s.label} className="rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 p-5 shadow-xl">
                                    <p className="text-2xl font-black text-white sm:text-3xl">{s.number}</p>
                                    <p className="mt-1 text-xs font-semibold text-white/80">{s.label}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Cutoff block */}
                {(c.cutoffGeneral || c.cutoffObc) && (
                    <section className="border-b border-border bg-card/40">
                        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
                            <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                                <Target className="mr-1 inline h-3 w-3" /> {c.year} Cutoff
                            </Badge>
                            <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                                Category-wise {c.examName} {c.year} qualifying marks
                            </h2>
                            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                                {[
                                    { label: 'General', value: c.cutoffGeneral },
                                    { label: 'OBC', value: c.cutoffObc },
                                    { label: 'SC', value: c.cutoffSc },
                                    { label: 'ST', value: c.cutoffSt },
                                    { label: 'PwD', value: c.cutoffPwD },
                                ]
                                    .filter((r) => typeof r.value === 'number')
                                    .map((r) => (
                                        <div key={r.label} className="rounded-2xl border border-border bg-card p-5 text-center">
                                            <p className="text-3xl font-black text-foreground">{r.value}</p>
                                            <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{r.label}</p>
                                        </div>
                                    ))}
                            </div>
                        </div>
                    </section>
                )}

                {/* Subject distribution */}
                <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <BarChart3 className="mr-1 inline h-3 w-3" /> Subject Distribution
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                        Subject-wise weightage in {c.examName} {c.year}
                    </h2>
                    <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {c.topSubjects.map((s) => (
                            <Card key={s.name} className="border-border/60 bg-card">
                                <CardContent className="p-5">
                                    <p className="text-sm font-bold text-foreground">{s.name}</p>
                                    <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
                                        <div
                                            className="h-full bg-linear-to-r from-primary to-teal-500"
                                            style={{ width: `${Math.min(100, (s.count / c.totalQuestions) * 100)}%` }}
                                        />
                                    </div>
                                    <p className="mt-2 text-xs font-semibold text-muted-foreground">{s.count} questions</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </section>

                {/* Year-specific high-yield observations — what makes this year UNIQUE */}
                <section className="border-y border-border bg-muted/30">
                    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            <Trophy className="mr-1 inline h-3 w-3" /> What made {c.year} unique
                        </Badge>
                        <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                            High-yield insights from {c.examName} {c.year}
                        </h2>
                        <ul className="mt-6 space-y-3">
                            {c.keyTrends.map((t, i) => (
                                <li key={i} className="flex items-start gap-3 rounded-2xl border border-border bg-card p-5">
                                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                                    <span className="text-sm leading-relaxed text-foreground">{t}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </section>

                {/* Toppers */}
                {c.toppers && c.toppers.length > 0 && (
                    <section className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            <Trophy className="mr-1 inline h-3 w-3" /> {c.year} Toppers
                        </Badge>
                        <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                            Top rankers in {c.examName} {c.year}
                        </h2>
                        <div className="mt-6 grid gap-3 sm:grid-cols-2">
                            {c.toppers.map((t) => (
                                <div key={t.name} className="rounded-2xl border border-border bg-card p-5">
                                    <p className="text-sm font-bold text-foreground">{t.name}</p>
                                    <p className="text-xs font-semibold text-primary">Score: {t.score}</p>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* FAQ */}
                <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6">
                    <FAQSection items={c.faqs} title={`${c.examName} ${c.year} — Frequently asked questions`} />
                </section>

                {/* CTA */}
                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <div className="rounded-3xl border border-primary/30 bg-linear-to-br from-primary/10 via-accent/30 to-teal-500/10 p-8 sm:p-12 text-center">
                        <h2 className="text-2xl font-black tracking-tight sm:text-3xl">
                            Practise {c.examName} {c.year} PYQs now
                        </h2>
                        <p className="mt-3 text-muted-foreground max-w-xl mx-auto">
                            Join thousands of medical aspirants using CrackCMS to prepare smarter. Start free today.
                        </p>
                        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                            <TrackedLink href="/register" eventName="register_intent" eventParams={{ source: 'pyq_landing' }}>
                                <Button size="lg" className="gap-2 font-bold">
                                    Create free account <ArrowRight className="h-4 w-4" />
                                </Button>
                            </TrackedLink>
                            <Link href={`/questions?exam=${c.examSlug.toUpperCase()}&year=${c.year}`}>
                                <Button size="lg" variant="outline" className="gap-2 font-bold">
                                    Open PYQ bank
                                </Button>
                            </Link>
                        </div>
                    </div>
                </section>
            </div>
        </>
    );
}
