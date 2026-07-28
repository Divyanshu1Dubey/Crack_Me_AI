import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { notFound } from 'next/navigation';
import { BookOpen, ChevronLeft } from 'lucide-react';
import { BlogCard } from '@/components/BlogCard';
import { Breadcrumbs } from '@/components/Breadcrumbs';
import { buildPageMetadata } from '@/lib/metadata';
import {
    getAllCategories,
    getPostsByCategory,
    categoryToSlug,
} from '@/lib/blog';
import { siteUrl } from '@/lib/seo';

interface PageProps {
    params: Promise<{ slug: string }>;
}

/** Statically generate a page for every category that has at least one post. */
export async function generateStaticParams() {
    return getAllCategories().map((c) => ({ slug: c.slug }));
}

/**
 * Category hub page (e.g. `/blog/category/upsc-cms`).
 *
 * Categorises posts by the `category` field on each post. Emits a
 * `CollectionPage` JSON-LD so the category hub itself can rank as a
 * standalone search-engine result.
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { slug } = await params;
    const cats = getAllCategories();
    const cat = cats.find((c) => c.slug === slug);
    if (!cat) {
        return buildPageMetadata({
            title: 'Category not found — CrackCMS Blog',
            description: 'No posts in this category yet.',
            path: `/blog/category/${slug}`,
            noindex: true,
        });
    }
    const title = `${cat.name} — CrackCMS Blog`;
    const description = `${cat.count} ${cat.count === 1 ? 'post' : 'posts'} on ${cat.name} strategy, mock-test tactics, high-yield revision and exam-day preparation for MBBS graduates.`;
    return buildPageMetadata({
        title,
        description,
        path: `/blog/category/${cat.slug}`,
        keywords: [cat.name, 'medical exam blog', 'UPSC CMS', 'NEET PG', 'Prep'],
    });
}

export default async function BlogCategoryPage({ params }: PageProps) {
    const { slug } = await params;
    const cats = getAllCategories();
    const cat = cats.find((c) => c.slug === slug);
    if (!cat) notFound();

    const posts = getPostsByCategory(cat.slug);
    const canonicalPath = `/blog/category/${cat.slug}`;

    const jsonLd = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: `${cat.name} — CrackCMS Blog`,
        description: `${cat.count} clinical exam preparation ${cat.count === 1 ? 'post' : 'posts'} on ${cat.name}.`,
        url: `${siteUrl}${canonicalPath}`,
        isPartOf: { '@type': 'Blog', name: 'CrackCMS Blog', url: `${siteUrl}/blog` },
        hasPart: posts.map((p) => ({
            '@type': 'BlogPosting',
            headline: p.title,
            url: `${siteUrl}/blog/${p.slug}`,
            datePublished: p.datePublished,
            dateModified: p.dateModified,
        })),
    };

    return (
        <>
            <Script
                id={`category-schema-${cat.slug}`}
                type="application/ld+json"
                strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
            />

            <div className="min-h-screen bg-background text-foreground">
                <section className="border-b border-border bg-linear-to-br from-indigo-600/10 via-background to-violet-600/10">
                    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
                        <Breadcrumbs
                            items={[
                                { name: 'Blog', path: '/blog' },
                                { name: 'Categories', path: '/blog' },
                                { name: cat.name, path: canonicalPath },
                            ]}
                        />
                        <Link
                            href="/blog"
                            className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground mb-5 mt-3"
                        >
                            <ChevronLeft className="h-3.5 w-3.5" /> All categories
                        </Link>

                        <div className="flex flex-wrap items-center gap-2 mb-4">
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-primary">
                                <BookOpen className="h-3 w-3" /> Category
                            </span>
                        </div>
                        <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            {cat.name}
                        </h1>
                        <p className="mt-4 max-w-3xl text-base text-muted-foreground">
                            {cat.count} {cat.count === 1 ? 'post' : 'posts'} on {cat.name} strategy,
                            mock-test scoring, high-yield revision and exam-day preparation for
                            MBBS graduates across India.
                        </p>
                    </div>
                </section>

                <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
                    {posts.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
                            No posts in this category yet. <Link href="/blog" className="text-primary hover:underline">Browse all posts →</Link>
                        </div>
                    ) : (
                        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                            {posts.map((p) => (
                                <BlogCard key={p.slug} post={p} />
                            ))}
                        </div>
                    )}

                    {/* Sibling categories — internal linking pass */}
                    <div className="mt-12 rounded-2xl border border-border bg-card p-5 sm:p-6">
                        <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-3">
                            Browse other categories
                        </h2>
                        <div className="flex flex-wrap gap-2">
                            {cats
                                .filter((c) => c.slug !== cat.slug)
                                .map((c) => (
                                    <Link
                                        key={c.slug}
                                        href={`/blog/category/${c.slug}`}
                                        className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-bold text-foreground hover:border-primary hover:text-primary transition-colors"
                                    >
                                        {c.name} ({c.count})
                                    </Link>
                                ))}
                        </div>
                    </div>
                </section>
            </div>
        </>
    );
}
