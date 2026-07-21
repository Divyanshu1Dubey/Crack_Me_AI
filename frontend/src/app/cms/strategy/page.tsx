import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import { getAllCmsStrategySlugs, ALL_STRATEGIES } from '@/lib/strategyData';
import Breadcrumbs from '@/components/Breadcrumbs';

export const metadata: Metadata = {
    title: 'UPSC CMS Study Plans — 6-Month, 3-Month, Last-Week | CrackCMS',
    description: 'UPSC CMS study plans built by UPSC CMS AIR-1. Choose your timeline — 6 months, 3 months, or last-week revision — and follow a precise day-by-day schedule.',
    alternates: { canonical: '/cms/strategy', languages: { 'en-IN': '/cms/strategy' } },
    openGraph: { type: 'website', url: '/cms/strategy', title: 'UPSC CMS Study Plans | CrackCMS', siteName },
    twitter: { card: 'summary_large_image', title: 'UPSC CMS Study Plans | CrackCMS' },
    robots: { index: true, follow: true },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'UPSC CMS Study Plans',
    description: 'Timeline-specific study plans for UPSC CMS.',
    url: `${siteUrl}/cms/strategy`,
    isPartOf: { '@type': 'WebSite', name: siteName, url: siteUrl },
};

export default function CMSStrategyIndexPage() {
    const slugs = getAllCmsStrategySlugs();
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Strategy', path: '/cms/strategy' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Study Plans
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Timeline-specific plans built by an UPSC CMS AIR-1. Pick your timeline below.
                    </p>
                </section>
                <section className="mx-auto grid max-w-5xl gap-3 px-4 pb-16 sm:px-6 sm:grid-cols-2 lg:grid-cols-3">
                    {slugs.map((slug) => {
                        const strat = ALL_STRATEGIES[slug];
                        return (
                            <Link key={slug} href={`/cms/strategy/${slug}`} className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{strat.durationLabel} plan</p>
                                <p className="mt-1 text-lg font-black text-foreground">{strat.strategyTitle}</p>
                                <p className="mt-2 text-xs text-muted-foreground">{strat.strategySubtitle}</p>
                                <p className="mt-3 text-sm font-semibold text-primary group-hover:underline">Open plan →</p>
                            </Link>
                        );
                    })}
                </section>
            </div>
        </>
    );
}