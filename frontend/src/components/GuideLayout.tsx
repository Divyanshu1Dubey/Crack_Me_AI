import type { Metadata } from 'next';
import Link from 'next/link';
import { TrackedLink } from '@/components/TrackedLink';
import Script from 'next/script';
import { ArrowLeft, CalendarDays, Clock, User, BookOpen, GraduationCap } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';

interface GuideLayoutProps {
    /** SEO title */
    title: string;
    /** SEO description */
    description: string;
    /** URL slug, e.g. 'upsc-cms-guide' */
    slug: string;
    /** Display title in hero */
    heading: string;
    /** Lede / subheading */
    lede: string;
    /** Author name */
    author: string;
    /** Last updated date */
    lastUpdated: string;
    /** Reading time in minutes */
    readingTime: string;
    /** FAQ items for schema */
    faqs?: { q: string; a: string }[];
    /** Article schema @type — defaults to Article */
    articleType?: string;
    children: React.ReactNode;
}

export function buildGuideMetadata({
    title,
    description,
    slug,
}: Pick<GuideLayoutProps, 'title' | 'description' | 'slug'>): Metadata {
    const canonical = `/guides/${slug}`;
    return {
        title,
        description,
        keywords: [title, 'medical exam', 'UPSC CMS', 'NEET PG', 'crack CMS', 'crack NEET PG'],
        alternates: { canonical, languages: { 'en-IN': canonical } },
        openGraph: {
            type: 'article',
            url: canonical,
            title,
            description,
            siteName,
            images: [{ url: '/cms-circle-logo.png', width: 1200, height: 630, alt: title }],
        },
        twitter: { card: 'summary_large_image', title, description },
        robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-snippet': -1, 'max-image-preview': 'large' } },
    };
}

export function GuideLayout({
    title,
    description,
    slug,
    heading,
    lede,
    author,
    lastUpdated,
    readingTime,
    faqs = [],
    articleType = 'Article',
    children,
}: GuideLayoutProps) {
    const canonical = `/guides/${slug}`;
    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': articleType,
                headline: heading,
                description,
                url: canonical,
                datePublished: lastUpdated,
                dateModified: lastUpdated,
                inLanguage: 'en-IN',
                author: { '@type': 'Person', name: author },
                publisher: {
                    '@type': 'Organization',
                    name: siteName,
                    url: siteUrl,
                    logo: { '@type': 'ImageObject', url: `${siteUrl}/cms-circle-logo.png` },
                },
                mainEntityOfPage: { '@type': 'WebPage', '@id': canonical },
            },
            ...(faqs.length > 0 ? [{
                '@type': 'FAQPage',
                mainEntity: faqs.map(f => ({
                    '@type': 'Question',
                    name: f.q,
                    acceptedAnswer: { '@type': 'Answer', text: f.a },
                })),
            }] : []),
            {
                '@type': 'BreadcrumbList',
                itemListElement: [
                    { '@type': 'ListItem', position: 1, name: 'Home', item: siteUrl },
                    { '@type': 'ListItem', position: 2, name: 'Guides', item: `${siteUrl}/guides` },
                    { '@type': 'ListItem', position: 3, name: heading, item: `${siteUrl}${canonical}` },
                ],
            },
        ],
    };

    return (
        <>
            <Script id={`guide-schema-${slug}`} type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                {/* Hero */}
                <section className="border-b border-border bg-linear-to-br from-primary/8 via-background to-accent/10">
                    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
                        <Link href="/guides" className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground mb-5">
                            <ArrowLeft className="h-3.5 w-3.5" /> All guides
                        </Link>
                        <div className="flex flex-wrap items-center gap-2 mb-3">
                            <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                                <BookOpen className="h-3 w-3 mr-1" /> Guide
                            </Badge>
                        </div>
                        <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">{heading}</h1>
                        <p className="mt-4 text-lg text-muted-foreground">{lede}</p>
                        <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
                            <span className="inline-flex items-center gap-1.5">
                                <User className="h-3.5 w-3.5" /> By <strong className="text-foreground">{author}</strong>
                            </span>
                            <span className="inline-flex items-center gap-1.5">
                                <CalendarDays className="h-3.5 w-3.5" /> Updated <strong className="text-foreground">{lastUpdated}</strong>
                            </span>
                            <span className="inline-flex items-center gap-1.5">
                                <Clock className="h-3.5 w-3.5" /> <strong className="text-foreground">{readingTime}</strong> read
                            </span>
                        </div>
                    </div>
                </section>

                {/* Body */}
                <article className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
                    <div className="legal-content">{children}</div>

                    {/* FAQs */}
                    {faqs.length > 0 && (
                        <section className="mt-12 rounded-2xl border border-border bg-card p-6 sm:p-8">
                            <h2 className="text-xl font-bold flex items-center gap-2">
                                <GraduationCap className="h-5 w-5 text-primary" />
                                Frequently asked questions
                            </h2>
                            <div className="mt-5 space-y-3">
                                {faqs.map((f, i) => (
                                    <details key={f.q} className="rounded-xl border border-border bg-background p-4 open:bg-accent/30" open={i === 0}>
                                        <summary className="cursor-pointer text-sm font-bold text-foreground list-none">{f.q}</summary>
                                        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
                                    </details>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* CTA */}
                    <Card className="mt-12 border-primary/30 bg-linear-to-br from-primary/10 via-accent/20 to-teal-500/10">
                        <CardContent className="p-6 sm:p-8 text-center">
                            <h3 className="text-lg font-bold">Ready to start practising?</h3>
                            <p className="mt-2 text-sm text-muted-foreground">
                                CrackCMS combines AI tutoring with 1,920+ PYQs and a full mock-test simulator.
                            </p>
                            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                                <TrackedLink href="/register" eventName="register_intent" eventParams={{ source: 'guide_layout' }} className="rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-95">Create free account</TrackedLink>
                                <Link href="/questions" className="rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground hover:bg-muted">Browse question bank</Link>
                            </div>
                        </CardContent>
                    </Card>
                </article>
            </div>
        </>
    );
}
