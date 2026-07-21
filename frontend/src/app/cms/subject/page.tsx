import type { Metadata } from 'next';
import Link from 'next/link';
import { siteName, siteUrl } from '@/lib/seo';
import { getAllCmsSubjects } from '@/lib/subjectHubData';
import Breadcrumbs from '@/components/Breadcrumbs';

export const metadata: Metadata = {
    title: 'UPSC CMS Subject Hubs — Medicine, Surgery, OBG, PSM, Paediatrics | CrackCMS',
    description:
        'Subject-wise UPSC CMS preparation. PYQs, high-yield topics, and book recommendations for General Medicine, Surgery, Paediatrics, OBG, PSM, ENT, Ophthalmology, Anaesthesia and Orthopaedics.',
    alternates: { canonical: '/cms/subject', languages: { 'en-IN': '/cms/subject' } },
    openGraph: {
        type: 'website',
        url: '/cms/subject',
        title: 'UPSC CMS Subject Hubs | CrackCMS',
        description: 'Subject-wise UPSC CMS PYQs, high-yield topics and book recommendations.',
        siteName,
    },
    twitter: { card: 'summary_large_image', title: 'UPSC CMS Subject Hubs | CrackCMS' },
    robots: { index: true, follow: true },
};

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'UPSC CMS Subject Hubs',
    description: 'Subject-wise UPSC CMS PYQ practice with high-yield topics and book recommendations.',
    url: `${siteUrl}/cms/subject`,
    isPartOf: { '@type': 'WebSite', name: siteName, url: siteUrl },
};

export default function CMSSubjectIndexPage() {
    const subjects = getAllCmsSubjects();
    const subjectMeta: Record<string, { name: string; qCount: number; weightPct: number }> = {
        medicine: { name: 'General Medicine', qCount: 96, weightPct: 40 },
        surgery: { name: 'General Surgery', qCount: 88, weightPct: 36 },
        paediatrics: { name: 'Paediatrics', qCount: 24, weightPct: 10 },
        obg: { name: 'Obstetrics & Gynaecology', qCount: 24, weightPct: 10 },
        psm: { name: 'Preventive & Social Medicine', qCount: 32, weightPct: 13 },
        ent: { name: 'ENT', qCount: 8, weightPct: 3 },
        ophthalmology: { name: 'Ophthalmology', qCount: 8, weightPct: 3 },
        anaesthesia: { name: 'Anaesthesia', qCount: 8, weightPct: 3 },
        orthopaedics: { name: 'Orthopaedics', qCount: 8, weightPct: 3 },
    };

    const itemList = subjects.map((slug, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: `${subjectMeta[slug]?.name ?? slug} PYQs`,
        url: `${siteUrl}/cms/subject/${slug}`,
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
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Subjects', path: '/cms/subject' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Subjects — Subject-wise PYQs & High-Yield Topics
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Pick a subject to see previous-year questions, the most-tested topics, recommended books,
                        and AI-powered explanations grounded in standard references.
                    </p>
                </section>
                <section className="mx-auto grid max-w-5xl gap-3 px-4 pb-16 sm:px-6 sm:grid-cols-2 lg:grid-cols-3">
                    {subjects.map((slug) => {
                        const meta = subjectMeta[slug];
                        if (!meta) return null;
                        return (
                            <Link
                                key={slug}
                                href={`/cms/subject/${slug}`}
                                className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md"
                            >
                                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{meta.weightPct}% weightage</p>
                                <p className="mt-1 text-xl font-black text-foreground">{meta.name}</p>
                                <p className="mt-2 text-sm font-semibold text-primary group-hover:underline">
                                    {meta.qCount} PYQs →
                                </p>
                            </Link>
                        );
                    })}
                </section>
            </div>
        </>
    );
}