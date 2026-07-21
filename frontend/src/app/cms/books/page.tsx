import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import { getAllCmsBookSlugs, CMS_BOOKS } from '@/lib/bookDeepDiveData';
import Breadcrumbs from '@/components/Breadcrumbs';

export const metadata: Metadata = {
    title: 'Best Books for UPSC CMS — Subject-wise Book Recommendations | CrackCMS',
    description: 'Top book recommendations for UPSC CMS by subject — Harrison, Bailey & Love, Park PSM, Ghai Paediatrics, Dutta OBG. Edition guide + reading schedules.',
    alternates: { canonical: '/cms/books', languages: { 'en-IN': '/cms/books' } },
    openGraph: { type: 'website', url: '/cms/books', title: 'Best Books for UPSC CMS | CrackCMS', siteName },
    twitter: { card: 'summary_large_image', title: 'Best Books for UPSC CMS | CrackCMS' },
    robots: { index: true, follow: true },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'Best Books for UPSC CMS',
    description: 'Subject-wise book recommendations for UPSC CMS.',
    url: `${siteUrl}/cms/books`,
    isPartOf: { '@type': 'WebSite', name: siteName, url: siteUrl },
};

export default function CMSBooksIndexPage() {
    const slugs = getAllCmsBookSlugs();
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Books', path: '/cms/books' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        Best Books for UPSC CMS
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Subject-wise book recommendations with high-yield chapters, 30-day reading plans, and
                        honest review by an UPSC CMS AIR-1 topper.
                    </p>
                </section>
                <section className="mx-auto grid max-w-5xl gap-3 px-4 pb-16 sm:px-6 sm:grid-cols-2 lg:grid-cols-3">
                    {slugs.map((slug) => {
                        const book = CMS_BOOKS[slug];
                        return (
                            <Link key={slug} href={`/cms/books/${slug}`} className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md">
                                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{book.subjectName}</p>
                                <p className="mt-1 text-base font-bold text-foreground leading-tight">{book.bookTitle}</p>
                                <p className="mt-1 text-xs text-muted-foreground">{book.bookEdition ?? ''}</p>
                                <p className="mt-3 text-sm font-semibold text-primary group-hover:underline">Read deep-dive →</p>
                            </Link>
                        );
                    })}
                </section>
            </div>
        </>
    );
}