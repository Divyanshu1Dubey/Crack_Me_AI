import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { siteName, siteUrl } from '@/lib/seo';
import { ArrowLeft, CalendarDays, FileText, ShieldCheck } from 'lucide-react';

interface LegalLayoutProps {
    title: string;
    description: string;
    lastUpdated: string;
    effectiveDate?: string;
    canonical: string;
    children: React.ReactNode;
    /** Schema.org @type — e.g. PrivacyPolicy, TermsOfService, MedicalWebPage */
    schemaType?: string;
}

/**
 * Shared layout for legal/policy pages. Renders an SEO-optimised article
 * with breadcrumb, last-updated timestamp, and inline JSON-LD Article
 * schema so each policy page ranks for its target query.
 */
export function buildLegalMetadata({
    title,
    description,
    canonical,
}: Pick<LegalLayoutProps, 'title' | 'description' | 'canonical'>): Metadata {
    return {
        title,
        description,
        alternates: {
            canonical,
            languages: {
                'en-IN': canonical,
                'en-US': canonical,
                'en-GB': canonical,
                'x-default': canonical,
            },
        },
        openGraph: {
            type: 'article',
            url: canonical,
            title,
            description,
            siteName,
        },
        twitter: {
            card: 'summary',
            title,
            description,
        },
        robots: {
            index: true,
            follow: true,
            googleBot: { index: true, follow: true, 'max-snippet': -1, 'max-image-preview': 'large' },
        },
    };
}

export function LegalLayout({
    title,
    description,
    lastUpdated,
    effectiveDate,
    canonical,
    children,
    schemaType = 'WebPage',
}: LegalLayoutProps) {
    const articleSchema = {
        '@context': 'https://schema.org',
        '@type': schemaType,
        headline: title,
        description,
        url: canonical,
        inLanguage: 'en-IN',
        datePublished: effectiveDate || lastUpdated,
        dateModified: lastUpdated,
        author: { '@type': 'Organization', name: siteName, url: siteUrl },
        publisher: {
            '@type': 'Organization',
            name: siteName,
            url: siteUrl,
            logo: { '@type': 'ImageObject', url: `${siteUrl}/cms-circle-logo.png` },
        },
        mainEntityOfPage: { '@type': 'WebPage', '@id': canonical },
        breadcrumb: {
            '@type': 'BreadcrumbList',
            itemListElement: [
                { '@type': 'ListItem', position: 1, name: 'Home', item: siteUrl },
                { '@type': 'ListItem', position: 2, name: title, item: canonical },
            ],
        },
    };

    return (
        <div className="min-h-screen bg-background text-foreground">
            <Script
                id={`legal-schema-${canonical.split('/').pop()}`}
                type="application/ld+json"
                strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }}
            />

            {/* Hero */}
            <section className="border-b border-border bg-gradient-to-br from-primary/8 via-background to-accent/10">
                <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16">
                    <Link
                        href="/"
                        className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground mb-6"
                    >
                        <ArrowLeft className="h-3.5 w-3.5" /> Back to home
                    </Link>
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                        <ShieldCheck className="h-3.5 w-3.5" /> Legal & Policy
                    </div>
                    <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        {title}
                    </h1>
                    <p className="mt-4 max-w-2xl text-base text-muted-foreground sm:text-lg">
                        {description}
                    </p>
                    <div className="mt-6 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1.5">
                            <CalendarDays className="h-3.5 w-3.5" /> Last updated: <strong className="text-foreground">{lastUpdated}</strong>
                        </span>
                        {effectiveDate && (
                            <span className="inline-flex items-center gap-1.5">
                                <FileText className="h-3.5 w-3.5" /> Effective: <strong className="text-foreground">{effectiveDate}</strong>
                            </span>
                        )}
                    </div>
                </div>
            </section>

            {/* Body */}
            <article className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
                <div className="prose prose-slate max-w-none dark:prose-invert legal-content">
                    {children}
                </div>

                {/* Related links — internal linking for SEO */}
                <aside className="mt-16 rounded-2xl border border-border bg-card p-6 sm:p-8">
                    <h2 className="text-lg font-bold">Related resources</h2>
                    <p className="mt-2 text-sm text-muted-foreground">
                        Continue exploring CrackCMS — your AI-powered medical exam preparation platform.
                    </p>
                    <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                        <li><Link href="/about" className="text-sm font-semibold text-primary hover:underline">About CrackCMS →</Link></li>
                        <li><Link href="/contact" className="text-sm font-semibold text-primary hover:underline">Contact support →</Link></li>
                        <li><Link href="/subscription" className="text-sm font-semibold text-primary hover:underline">Premium plans →</Link></li>
                        <li><Link href="/register" className="text-sm font-semibold text-primary hover:underline">Create a free account →</Link></li>
                    </ul>
                </aside>
            </article>
        </div>
    );
}
