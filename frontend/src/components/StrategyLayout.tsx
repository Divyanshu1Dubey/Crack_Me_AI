import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { ArrowRight, Calendar, CheckCircle2, Clock, GraduationCap, Sparkles, Target } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import FAQSection from '@/components/FAQSection';

export interface StrategyWeek {
    week: number;
    focus: string;
    hoursPerDay: number;
    milestones: string[];
}

export interface StrategyContent {
    examSlug: 'cms';
    examName: string;
    examLandingPath: string;
    strategySlug: '6-month' | '3-month' | 'last-week';
    strategyTitle: string;        // '6-Month UPSC CMS Study Plan'
    strategySubtitle: string;     // 'Built by UPSC CMS AIR-1'
    /** SEO description */
    description: string;
    /** Total study hours expected */
    totalHours: number;
    /** Total weeks (or 'Final 7 days') */
    durationLabel: string;
    /** Week-by-week plan */
    weeks: StrategyWeek[];
    /** Daily routine template */
    dailyRoutine: { time: string; activity: string }[];
    /** Subjects covered by week (for visualization) */
    subjectRotation: { subject: string; color: string }[];
    faqs: { q: string; a: string }[];
    reviewer: { name: string; credentials: string };
}

export function buildStrategyMetadata(c: StrategyContent, path: string): Metadata {
    const title = `${c.strategyTitle} — ${c.strategySubtitle} | CrackCMS`;
    return {
        title,
        description: c.description,
        alternates: { canonical: path, languages: { 'en-IN': path } },
        openGraph: { type: 'article', url: path, title, description: c.description, siteName },
        twitter: { card: 'summary_large_image', title, description: c.description },
        robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
    };
}

export default function StrategyLayout(c: StrategyContent) {
    const path = `/${c.examSlug}/strategy/${c.strategySlug}`;
    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'HowTo',
                headline: c.strategyTitle,
                description: c.description,
                inLanguage: 'en-IN',
                datePublished: '2025-01-01',
                dateModified: '2026-07-21',
                author: { '@type': 'Organization', name: siteName, url: siteUrl },
                publisher: { '@type': 'Organization', name: siteName, url: siteUrl },
                reviewedBy: { '@type': 'Person', name: c.reviewer.name, credentials: c.reviewer.credentials },
                mainEntityOfPage: { '@type': 'WebPage', '@id': `${siteUrl}${path}` },
                step: c.weeks.map((w) => ({
                    '@type': 'HowToStep',
                    position: w.week,
                    name: `Week ${w.week} — ${w.focus}`,
                    text: `${w.focus}. ${w.hoursPerDay} hours/day. Milestones: ${w.milestones.join('; ')}.`,
                })),
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
                    { '@type': 'ListItem', position: 3, name: 'Strategy', item: `${siteUrl}/${c.examSlug}/strategy` },
                    { '@type': 'ListItem', position: 4, name: c.strategyTitle, item: `${siteUrl}${path}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`strategy-${c.examSlug}-${c.strategySlug}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[
                        { name: c.examName, path: c.examLandingPath },
                        { name: 'Strategy', path: `/${c.examSlug}/strategy` },
                        { name: c.strategyTitle, path },
                    ]} />
                </div>

                <section className="bg-gradient-to-br from-indigo-600 to-violet-700 text-white">
                    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
                        <Badge className="bg-white/15 text-white border-white/30 backdrop-blur-sm text-xs font-bold uppercase tracking-wider">
                            <GraduationCap className="mr-1 inline h-3 w-3" /> Study plan
                        </Badge>
                        <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            {c.strategyTitle}
                        </h1>
                        <p className="mt-4 max-w-3xl text-base text-white/85 sm:text-lg">
                            {c.strategySubtitle}. {c.description}
                        </p>
                        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
                            {[
                                { number: `${c.totalHours}h`, label: 'Total study hours' },
                                { number: c.durationLabel, label: 'Duration' },
                                { number: `${c.weeks.length}`, label: 'Phases' },
                            ].map((s) => (
                                <div key={s.label} className="rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 p-4 shadow-xl">
                                    <p className="text-xl font-black text-white sm:text-2xl">{s.number}</p>
                                    <p className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-white/80">{s.label}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Daily routine */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <Clock className="mr-1 inline h-3 w-3" /> Daily routine template
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">A typical day in this plan</h2>
                    <div className="mt-6 overflow-hidden rounded-2xl border border-border bg-card">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-muted/40">
                                    <th className="px-4 py-3 text-left font-bold">Time</th>
                                    <th className="px-4 py-3 text-left font-bold">Activity</th>
                                </tr>
                            </thead>
                            <tbody>
                                {c.dailyRoutine.map((row, i) => (
                                    <tr key={i} className="border-t border-border/60">
                                        <td className="px-4 py-3 font-semibold whitespace-nowrap">{row.time}</td>
                                        <td className="px-4 py-3 text-foreground">{row.activity}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Weekly plan */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <Target className="mr-1 inline h-3 w-3" /> Week-by-week plan
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">What to do each phase</h2>
                    <div className="mt-6 space-y-4">
                        {c.weeks.map((w) => (
                            <Card key={w.week} className="border-border/60 bg-card">
                                <CardContent className="p-5">
                                    <div className="flex flex-wrap items-baseline gap-3">
                                        <p className="text-xs font-bold uppercase tracking-wider text-primary">Week {w.week}</p>
                                        <h3 className="text-base font-bold text-foreground">{w.focus}</h3>
                                        <p className="text-xs font-semibold text-muted-foreground ml-auto">{w.hoursPerDay}h/day</p>
                                    </div>
                                    <ul className="mt-4 space-y-1">
                                        {w.milestones.map((m, i) => (
                                            <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                                                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                                                {m}
                                            </li>
                                        ))}
                                    </ul>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </section>

                {/* Subject rotation */}
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
                    <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                        <Sparkles className="mr-1 inline h-3 w-3" /> Subject rotation
                    </Badge>
                    <h2 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">Subjects covered (in rotation)</h2>
                    <div className="mt-6 flex flex-wrap gap-2">
                        {c.subjectRotation.map((s) => (
                            <Badge key={s.subject} className={`${s.color} px-3 py-1 text-xs font-bold`}>{s.subject}</Badge>
                        ))}
                    </div>
                </section>

                {/* FAQ */}
                <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6">
                    <FAQSection items={c.faqs} title={`${c.strategyTitle} — FAQs`} />
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <div className="rounded-3xl border border-primary/30 bg-gradient-to-br from-primary/10 via-accent/30 to-teal-500/10 p-8 text-center">
                        <h2 className="text-2xl font-black tracking-tight">Start practising today</h2>
                        <p className="mt-3 text-muted-foreground max-w-xl mx-auto">PYQs from every UPSC CMS year with AI-powered explanations.</p>
                        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/register">
                                <Button size="lg" className="gap-2 font-bold">Create free account <ArrowRight className="h-4 w-4" /></Button>
                            </Link>
                            <Link href={`/questions?exam=CMS`}>
                                <Button size="lg" variant="outline" className="gap-2 font-bold">Open Question Bank</Button>
                            </Link>
                        </div>
                    </div>
                    <p className="mt-6 text-center text-xs text-muted-foreground">
                        Plan designed by <span className="font-semibold text-foreground">{c.reviewer.name}</span>, {c.reviewer.credentials}. Last updated 21 July 2026.
                    </p>
                </section>
            </div>
        </>
    );
}