import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import { getAllCmsCutoffYears } from '@/lib/cutoffData';
import Breadcrumbs from '@/components/Breadcrumbs';

export const metadata: Metadata = {
    title: 'UPSC CMS Cutoff Marks by Year — 2020 to 2024 | CrackCMS',
    description: 'Category-wise UPSC CMS cutoff marks for the last 5 years. General, OBC, SC, ST, PwD cutoffs side-by-side, plus toppers and trend analysis.',
    alternates: { canonical: '/cms/cutoff', languages: { 'en-IN': '/cms/cutoff' } },
    openGraph: { type: 'website', url: '/cms/cutoff', title: 'UPSC CMS Cutoff Marks by Year | CrackCMS', description: 'Category-wise UPSC CMS cutoff marks 2020-2024.', siteName },
    twitter: { card: 'summary_large_image', title: 'UPSC CMS Cutoff Marks by Year | CrackCMS' },
    robots: { index: true, follow: true },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'UPSC CMS Cutoff Marks by Year',
    description: 'Year-wise category cutoffs for UPSC CMS.',
    url: `${siteUrl}/cms/cutoff`,
    isPartOf: { '@type': 'WebSite', name: siteName, url: siteUrl },
};

export default function CMSCutoffIndexPage() {
    const years = getAllCmsCutoffYears();
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Cutoff', path: '/cms/cutoff' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Cutoff Marks by Year
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Pick a year to see category-wise cutoff, topper scores, and year-over-year trend.
                        Source: official UPSC press releases.
                    </p>
                </section>
                <section className="mx-auto grid max-w-5xl gap-3 px-4 pb-16 sm:px-6 sm:grid-cols-2 lg:grid-cols-5">
                    {years.map((year) => (
                        <Link key={year} href={`/cms/cutoff/${year}`} className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Year</p>
                            <p className="mt-1 text-3xl font-black text-foreground">{year}</p>
                            <p className="mt-3 text-sm font-semibold text-primary group-hover:underline">Cutoff details →</p>
                        </Link>
                    ))}
                </section>
            </div>
        </>
    );
}