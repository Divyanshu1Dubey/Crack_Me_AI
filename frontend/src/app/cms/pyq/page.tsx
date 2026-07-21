import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import { getAllCmsYears } from '@/lib/pyqYearData';
import Breadcrumbs from '@/components/Breadcrumbs';

export const metadata: Metadata = {
    title: 'UPSC CMS Previous Year Questions (PYQs) by Year — 2020-2024 | CrackCMS',
    description:
        'Practise every UPSC CMS previous year question from 2020 to 2024. Year-wise PYQ papers with subject-wise filters, cutoffs, toppers, and AI explanations.',
    alternates: { canonical: '/cms/pyq', languages: { 'en-IN': '/cms/pyq' } },
    openGraph: {
        type: 'website',
        url: '/cms/pyq',
        title: 'UPSC CMS Previous Year Questions (PYQs) by Year | CrackCMS',
        description: 'Year-wise UPSC CMS PYQs with cutoffs, toppers, and AI explanations.',
        siteName,
    },
    twitter: { card: 'summary_large_image', title: 'UPSC CMS PYQs by Year | CrackCMS', description: 'Year-wise UPSC CMS PYQs with cutoffs, toppers, and AI explanations.' },
    robots: { index: true, follow: true },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'UPSC CMS Previous Year Questions by Year',
    description: 'Year-wise UPSC CMS PYQ practice with subject filters, cutoffs, and AI explanations.',
    url: `${siteUrl}/cms/pyq`,
    isPartOf: { '@type': 'WebSite', name: siteName, url: siteUrl },
};

export default function CMSPyqIndexPage() {
    const years = getAllCmsYears();
    const itemList = years.map((year, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: `UPSC CMS ${year} PYQs`,
        url: `${siteUrl}/cms/pyq/${year}`,
    }));

    return (
        <>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{
                    __html: JSON.stringify({
                        ...jsonLd,
                        mainEntity: {
                            '@type': 'ItemList',
                            itemListElement: itemList,
                        },
                    }),
                }}
            />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'PYQs', path: '/cms/pyq' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Previous Year Questions by Year
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Pick a year to practise the full UPSC CMS paper with subject filters, AI explanations,
                        cutoffs, and topper scores. Updated within 24 hours of every UPSC notification.
                    </p>
                </section>
                <section className="mx-auto grid max-w-5xl gap-4 px-4 pb-16 sm:px-6 sm:grid-cols-2 lg:grid-cols-3">
                    {years.map((year) => (
                        <Link
                            key={year}
                            href={`/cms/pyq/${year}`}
                            className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-md"
                        >
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Year</p>
                            <p className="mt-1 text-4xl font-black text-foreground">{year}</p>
                            <p className="mt-3 text-sm font-semibold text-primary group-hover:underline">
                                Practise 240 PYQs →
                            </p>
                        </Link>
                    ))}
                </section>
            </div>
        </>
    );
}
