import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { CheckCircle2, Sparkles, Target, BookOpen, Brain, FileText, Trophy, Zap, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';

export interface ExamLandingContent {
    /** URL slug, e.g. 'cms' -> /cms */
    slug: string;
    /** Display name, e.g. 'UPSC CMS' */
    name: string;
    /** Full title, e.g. 'Combined Medical Services Examination' */
    fullName: string;
    /** SEO title */
    title: string;
    /** SEO description */
    description: string;
    /** One-liner for hero */
    tagline: string;
    /** Hero bullets */
    heroBullets: string[];
    /** Stat tiles */
    stats: { number: string; label: string }[];
    /** Pattern table rows */
    pattern: { label: string; value: string }[];
    /** Eligibility table rows */
    eligibility: { label: string; value: string }[];
    /** Syllabus table rows */
    syllabus: { subject: string; weight: string; topics: string }[];
    /** Books recommendations */
    books: { name: string; author: string; why: string }[];
    /** FAQ items */
    faqs: { q: string; a: string }[];
    /** Hero accent gradient classes */
    accentFrom: string;
    accentTo: string;
    /** Badge emoji */
    emoji?: string;
    /** Number of PYQs in our bank for this exam */
    pyqCount: string;
}

interface ExamLandingLayoutProps extends ExamLandingContent {
    children?: React.ReactNode;
}

export function buildExamMetadata(c: ExamLandingContent): Metadata {
    const canonical = `/${c.slug}`;
    return {
        title: c.title,
        description: c.description,
        keywords: [
            `${c.name} preparation`,
            `${c.name} PYQ`,
            `${c.name} mock test`,
            `${c.name} syllabus`,
            `${c.name} previous year questions`,
            `${c.name} question bank`,
            `${c.name} exam pattern`,
            `${c.name} eligibility`,
            `${c.name} cutoff`,
            `${c.name} books`,
            'medical exam preparation',
            'AI medical tutor',
        ],
        alternates: {
            canonical,
            languages: { 'en-IN': canonical },
        },
        openGraph: {
            type: 'website',
            url: canonical,
            title: c.title,
            description: c.description,
            siteName,
            images: [{ url: '/cms-circle-logo.png', width: 1200, height: 630, alt: `${c.name} preparation on CrackCMS` }],
        },
        twitter: {
            card: 'summary_large_image',
            title: c.title,
            description: c.description,
        },
        robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-snippet': -1, 'max-image-preview': 'large' } },
    };
}

export function ExamLandingLayout(c: ExamLandingContent) {
    const canonical = `/${c.slug}`;

    // JSON-LD: Course + FAQPage + BreadcrumbList
    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'Course',
                name: `${c.name} Complete Preparation Course`,
                description: c.description,
                provider: { '@type': 'Organization', name: siteName, url: siteUrl },
                url: canonical,
                educationalLevel: 'Postgraduate',
                inLanguage: 'en-IN',
                hasCourseInstance: {
                    '@type': 'CourseInstance',
                    courseMode: 'online',
                    courseSchedule: { '@type': 'Schedule', repeatFrequency: 'P1D' },
                },
                offers: {
                    '@type': 'Offer',
                    price: '199',
                    priceCurrency: 'INR',
                    availability: 'https://schema.org/InStock',
                },
            },
            {
                '@type': 'FAQPage',
                mainEntity: c.faqs.map(f => ({
                    '@type': 'Question',
                    name: f.q,
                    acceptedAnswer: { '@type': 'Answer', text: f.a },
                })),
            },
            {
                '@type': 'BreadcrumbList',
                itemListElement: [
                    { '@type': 'ListItem', position: 1, name: 'Home', item: siteUrl },
                    { '@type': 'ListItem', position: 2, name: c.name, item: `${siteUrl}${canonical}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`exam-schema-${c.slug}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                {/* ─── HERO ─── */}
                <section className={`relative overflow-hidden border-b border-border bg-gradient-to-br ${c.accentFrom} ${c.accentTo}`}>
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.15),transparent_55%)] pointer-events-none" />
                    <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 md:py-20 lg:grid-cols-2 lg:gap-16 lg:py-24">
                        <div>
                            <Badge className="bg-white/20 text-white border-white/30 backdrop-blur-sm text-xs font-bold uppercase tracking-wider">
                                {c.emoji || '🎯'} {c.fullName}
                            </Badge>
                            <h1 className="mt-4 text-3xl font-black tracking-tight text-white sm:text-4xl md:text-5xl lg:text-6xl">
                                Crack {c.name} with <span className="text-yellow-300">AI-powered</span> prep
                            </h1>
                            <p className="mt-4 max-w-xl text-base text-white/85 sm:text-lg">{c.tagline}</p>
                            <ul className="mt-6 space-y-2">
                                {c.heroBullets.map(b => (
                                    <li key={b} className="flex items-start gap-2 text-sm text-white/90">
                                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-yellow-300" />
                                        <span>{b}</span>
                                    </li>
                                ))}
                            </ul>
                            <div className="mt-8 flex flex-wrap gap-3">
                                <Link href="/register">
                                    <Button size="lg" className="bg-white text-slate-900 hover:bg-white/90 font-bold gap-2 shadow-lg">
                                        Start Free <ArrowRight className="h-4 w-4" />
                                    </Button>
                                </Link>
                                <Link href="/questions">
                                    <Button size="lg" variant="outline" className="border-white/40 bg-white/10 text-white hover:bg-white/20 backdrop-blur-sm font-bold gap-2">
                                        <BookOpen className="h-4 w-4" /> Try PYQs
                                    </Button>
                                </Link>
                            </div>
                            <p className="mt-4 text-xs text-white/70">
                                No credit card needed · 10 free AI tokens daily · Cancel anytime
                            </p>
                        </div>

                        {/* Stats card */}
                        <div className="grid grid-cols-2 gap-3 sm:gap-4 self-center">
                            {c.stats.map(s => (
                                <div key={s.label} className="rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 p-5 sm:p-6 shadow-xl">
                                    <p className="text-3xl sm:text-4xl font-black text-white">{s.number}</p>
                                    <p className="mt-1 text-xs sm:text-sm font-semibold text-white/80">{s.label}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* ─── STAT TILES (light) ─── */}
                <section className="border-b border-border bg-card/50">
                    <div className="mx-auto grid max-w-7xl grid-cols-2 gap-px bg-border sm:grid-cols-4">
                        {c.stats.map(s => (
                            <div key={`b-${s.label}`} className="bg-card p-5 sm:p-6 text-center">
                                <p className="text-2xl font-black text-foreground sm:text-3xl">{s.number}</p>
                                <p className="mt-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">{s.label}</p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* ─── WHY CRACKCMS ─── */}
                <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
                    <div className="text-center mb-10">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            Why CrackCMS
                        </Badge>
                        <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl md:text-4xl">
                            Everything you need to crack {c.name}, in one app
                        </h2>
                    </div>
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {[
                            { icon: Brain, title: 'AI tutor', body: `Personalised explanations, mnemonics and clinical pearls for every ${c.name} question.` },
                            { icon: FileText, title: `${c.pyqCount} PYQs`, body: 'Previous-year questions with step-by-step solutions, sorted by subject, topic and year.' },
                            { icon: Target, title: 'Adaptive tests', body: 'Mock tests that mirror the real exam pattern, with negative marking and real-time ranking.' },
                            { icon: BookOpen, title: 'Textbook-linked', body: 'Every answer links to Harrison, Bailey & Love, Ghai, Park, Nelson and other standard texts.' },
                            { icon: Trophy, title: 'Gamified streaks', body: 'Daily streaks, badges, leaderboards and XP to keep you consistent for 6 months.' },
                            { icon: Zap, title: 'Offline-friendly', body: 'PWAs and an Android wrapper let you revise PYQs even without internet.' },
                        ].map(f => (
                            <Card key={f.title} className="border-border/60 bg-card">
                                <CardContent className="p-6">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                        <f.icon className="h-5 w-5" />
                                    </div>
                                    <h3 className="mt-3 text-base font-bold text-foreground">{f.title}</h3>
                                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </section>

                {/* ─── EXAM PATTERN ─── */}
                <section className="border-y border-border bg-muted/30">
                    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
                        <div className="grid gap-10 lg:grid-cols-2">
                            <div>
                                <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                                    Exam Pattern
                                </Badge>
                                <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                                    Latest {c.name} paper structure
                                </h2>
                                <p className="mt-3 text-muted-foreground">
                                    CrackCMS mock tests follow the official {c.name} pattern so you practise
                                    in the exact format you&apos;ll face on exam day.
                                </p>
                                <Link href="/simulator">
                                    <Button className="mt-6 gap-2">
                                        Try the simulator <ArrowRight className="h-4 w-4" />
                                    </Button>
                                </Link>
                            </div>
                            <div className="rounded-2xl border border-border bg-card overflow-hidden">
                                <table className="w-full text-sm">
                                    <tbody>
                                        {c.pattern.map(row => (
                                            <tr key={row.label} className="border-b border-border last:border-0">
                                                <th className="px-4 py-3 text-left font-semibold text-foreground bg-muted/50 w-1/2">{row.label}</th>
                                                <td className="px-4 py-3 text-foreground">{row.value}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </section>

                {/* ─── ELIGIBILITY ─── */}
                <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        Eligibility
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                        Who can apply for {c.name}?
                    </h2>
                    <div className="mt-6 rounded-2xl border border-border bg-card overflow-hidden">
                        <table className="w-full text-sm">
                            <tbody>
                                {c.eligibility.map(row => (
                                    <tr key={row.label} className="border-b border-border last:border-0">
                                        <th className="px-4 py-3 text-left font-semibold text-foreground bg-muted/50 w-1/3">{row.label}</th>
                                        <td className="px-4 py-3 text-foreground">{row.value}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* ─── SYLLABUS ─── */}
                <section className="border-y border-border bg-muted/30">
                    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            Syllabus
                        </Badge>
                        <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                            High-yield {c.name} syllabus, broken down by subject
                        </h2>
                        <div className="mt-6 rounded-2xl border border-border bg-card overflow-hidden">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="bg-muted/60">
                                        <th className="px-4 py-3 text-left font-semibold">Subject</th>
                                        <th className="px-4 py-3 text-left font-semibold w-24">Weight</th>
                                        <th className="px-4 py-3 text-left font-semibold">High-yield topics</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {c.syllabus.map(row => (
                                        <tr key={row.subject} className="border-b border-border last:border-0">
                                            <td className="px-4 py-3 font-semibold text-foreground">{row.subject}</td>
                                            <td className="px-4 py-3 font-bold text-primary">{row.weight}</td>
                                            <td className="px-4 py-3 text-muted-foreground">{row.topics}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                {/* ─── BOOKS ─── */}
                <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        Recommended Books
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                        Standard textbooks for {c.name}
                    </h2>
                    <div className="mt-6 grid gap-4 md:grid-cols-2">
                        {c.books.map(b => (
                            <Card key={b.name} className="border-border/60 bg-card">
                                <CardContent className="p-5">
                                    <h3 className="text-base font-bold text-foreground">{b.name}</h3>
                                    <p className="text-xs font-semibold text-primary uppercase tracking-wider">{b.author}</p>
                                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{b.why}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </section>

                {/* ─── FAQ ─── */}
                <section className="border-t border-border bg-muted/30">
                    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16">
                        <div className="text-center mb-10">
                            <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                                FAQ
                            </Badge>
                            <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                                Frequently asked questions about {c.name}
                            </h2>
                        </div>
                        <div className="space-y-3">
                            {c.faqs.map((f, i) => (
                                <details
                                    key={f.q}
                                    className="group rounded-2xl border border-border bg-card p-5 open:shadow-sm transition-shadow"
                                    open={i === 0}
                                >
                                    <summary className="flex cursor-pointer items-start justify-between gap-3 text-sm font-bold text-foreground list-none">
                                        <span>{f.q}</span>
                                        <span className="text-muted-foreground text-xl leading-none group-open:rotate-45 transition-transform">+</span>
                                    </summary>
                                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
                                </details>
                            ))}
                        </div>
                    </div>
                </section>

                {/* ─── CTA ─── */}
                <section className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
                    <div className="rounded-3xl border border-primary/30 bg-gradient-to-br from-primary/10 via-accent/30 to-teal-500/10 p-8 sm:p-12 text-center">
                        <Sparkles className="mx-auto h-10 w-10 text-primary" />
                        <h2 className="mt-4 text-2xl font-black tracking-tight sm:text-3xl">
                            Ready to crack {c.name}?
                        </h2>
                        <p className="mt-3 text-muted-foreground max-w-xl mx-auto">
                            Join 47,000+ medical aspirants using CrackCMS to prepare smarter. Start free today.
                        </p>
                        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/register" onClick={() => {
                                if (typeof window !== 'undefined' && (window as any).gtag) {
                                    (window as any).gtag('event', 'register_intent', { source: 'exam_landing' });
                                }
                            }}>
                                <Button size="lg" className="gap-2 font-bold">
                                    Create free account <ArrowRight className="h-4 w-4" />
                                </Button>
                            </Link>
                            <Link href="/subscription">
                                <Button size="lg" variant="outline" className="gap-2 font-bold">
                                    See premium plans
                                </Button>
                            </Link>
                        </div>
                    </div>
                </section>

                {/* ─── RELATED EXAMS ─── */}
                <section className="border-t border-border bg-card/50">
                    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
                        <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Explore other exams</h3>
                        <div className="mt-4 flex flex-wrap gap-2">
                            <Link href="/cms" className="rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:border-primary hover:text-primary">UPSC CMS</Link>
                            <Link href="/neet-pg" className="rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:border-primary hover:text-primary">NEET PG</Link>
                            <Link href="/ini-cet" className="rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:border-primary hover:text-primary">INI-CET</Link>
                            <Link href="/fmge" className="rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:border-primary hover:text-primary">FMGE</Link>
                            <Link href="/usmle" className="rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:border-primary hover:text-primary">USMLE</Link>
                            <Link href="/medical-officer" className="rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:border-primary hover:text-primary">Medical Officer</Link>
                        </div>
                    </div>
                </section>
            </div>
        </>
    );
}
