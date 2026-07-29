import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { notFound } from 'next/navigation';
import { ChevronLeft, Hash } from 'lucide-react';
import { BlogCard } from '@/components/BlogCard';
import Breadcrumbs from '@/components/Breadcrumbs';
import { buildPageMetadata } from '@/lib/metadata';
import { getAllTags, getPostsByTag, tagToSlug } from '@/lib/blog';
import { siteUrl } from '@/lib/seo';

interface PageProps {
    params: Promise<{ slug: string }>;
}

/** Pre-render every tag page that has at least one post. */
export async function generateStaticParams() {
    return getAllTags().map((t) => ({ slug: t.slug }));
}

/**
 * Tag archive page (e.g. `/blog/tag/last-5-days`).
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { slug } = await params;
    const tag = getAllTags().find((t) => t.slug === slug);
    if (!tag) {
        return buildPageMetadata({
            title: 'Tag not found — CrackCMS Blog',
            description: 'No posts with this tag.',
            path: `/blog/tag/${slug}`,
            noindex: true,
        });
    }
    return buildPageMetadata({
        title: `#${tag.name} — CrackCMS Blog`,
        description: `${tag.count} ${tag.count === 1 ? 'post' : 'posts'} tagged #${tag.name} on UPSC CMS, NEET PG and INI-CET preparation.`,
        path: `/blog/tag/${tag.slug}`,
    });
}

export default async function BlogTagPage({ params }: PageProps) {
    const { slug } = await params;
    const tag = getAllTags().find((t) => t.slug === slug);
    if (!tag) notFound();

    const posts = getPostsByTag(tag.slug);
    const canonicalPath = `/blog/tag/${tag.slug}`;

    const jsonLd = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: `#${tag.name} — CrackCMS Blog`,
        description: `${tag.count} posts tagged ${tag.name}.`,
        url: `${siteUrl}${canonicalPath}`,
        isPartOf: { '@type': 'Blog', name: 'CrackCMS Blog', url: `${siteUrl}/blog` },
    };

    return (
        <>
            <Script
                id={`tag-schema-${tag.slug}`}
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
                                { name: 'Tags', path: '/blog' },
                                { name: `#${tag.name}`, path: canonicalPath },
                            ]}
                        />
                        <Link
                            href="/blog"
                            className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground mb-5 mt-3"
                        >
                            <ChevronLeft className="h-3.5 w-3.5" /> All tags
                        </Link>

                        <div className="flex flex-wrap items-center gap-2 mb-4">
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-primary">
                                <Hash className="h-3 w-3" /> Tag
                            </span>
                        </div>
                        <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            #{tag.name}
                        </h1>
                        <p className="mt-4 max-w-3xl text-base text-muted-foreground">
                            {tag.count} {tag.count === 1 ? 'post' : 'posts'} tagged with this topic.
                        </p>
                    </div>
                </section>

                <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
                    {posts.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
                            No posts with this tag. <Link href="/blog" className="text-primary hover:underline">Browse all posts →</Link>
                        </div>
                    ) : (
                        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                            {posts.map((p) => (
                                <BlogCard key={p.slug} post={p} />
                            ))}
                        </div>
                    )}

                    {/* Other tags — internal linking pass */}
                    <div className="mt-12 rounded-2xl border border-border bg-card p-5 sm:p-6">
                        <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-3">
                            Browse other tags
                        </h2>
                        <div className="flex flex-wrap gap-2">
                            {getAllTags()
                                .filter((t) => t.slug !== tag.slug)
                                .map((t) => (
                                    <Link
                                        key={t.slug}
                                        href={`/blog/tag/${t.slug}`}
                                        className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-bold text-foreground hover:border-primary hover:text-primary transition-colors"
                                    >
                                        #{t.name} ({t.count})
                                    </Link>
                                ))}
                        </div>
                    </div>
                </section>
            </div>
        </>
    );
}
