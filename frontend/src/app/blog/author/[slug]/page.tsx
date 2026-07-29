import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { notFound } from 'next/navigation';
import { ChevronLeft, GraduationCap, User } from 'lucide-react';
import { BlogCard } from '@/components/BlogCard';
import Breadcrumbs from "@/components/Breadcrumbs";
import { buildPageMetadata, personSchema } from '@/lib/metadata';
import { getAllPosts } from '@/lib/blog';
import { getAuthor } from '@/content/authors';
import { siteUrl } from '@/lib/seo';

interface PageProps {
    params: Promise<{ slug: string }>;
}

/** Pre-render every author profile that has at least one post. */
export async function generateStaticParams() {
    const slugs = new Set<string>();
    for (const p of getAllPosts()) {
        if (p.authorId) slugs.add(p.authorId);
        if (p.reviewedBy) slugs.add(p.reviewedBy);
    }
    return Array.from(slugs).map((slug) => ({ slug }));
}

/**
 * Author archive page. Emits a `Person` JSON-LD entity so the author
 * profile itself becomes a crawlable node in Google's knowledge graph.
 *
 * If the slug is unknown but matches a registered Profile nonetheless
 * (e.g. an author with no posts yet), we still render the profile as
 * a placeholder.
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { slug } = await params;
    const author = getAuthor(slug);
    return buildPageMetadata({
        title: `${author.name} — ${author.credential} — CrackCMS Blog`,
        description: author.bio,
        path: `/blog/author/${author.slug}`,
        keywords: [author.name, author.credential, ...author.expertise],
    });
}

export default async function BlogAuthorPage({ params }: PageProps) {
    const { slug } = await params;
    const author = getAuthor(slug);
    // Bail if the slug isn't a registered author at all (defensive — the
    // fallback `getAuthor` returns the editorial team for unknown slugs).
    if (!author || author.slug !== slug) notFound();

    const all = getAllPosts();
    const posts = all.filter((p) => p.authorId === author.slug);
    const reviewed = all.filter((p) => p.reviewedBy === author.slug && p.authorId !== author.slug);

    const canonicalPath = `/blog/author/${author.slug}`;
    const jsonLd = {
        '@context': 'https://schema.org',
        '@graph': [
            personSchema({
                name: author.name,
                credential: author.credential,
                role: author.role,
                bio: author.bio,
                expertise: author.expertise,
                sameAs: author.sameAs,
                url: `${siteUrl}${canonicalPath}`,
            }),
            {
                '@type': 'ProfilePage',
                mainEntity: { '@id': `${siteUrl}${canonicalPath}#person` },
                url: `${siteUrl}${canonicalPath}`,
                name: `${author.name} — Author profile`,
                isPartOf: { '@type': 'Blog', name: 'CrackCMS Blog', url: `${siteUrl}/blog` },
            },
        ],
    };

    return (
        <>
            <Script
                id={`author-schema-${author.slug}`}
                type="application/ld+json"
                strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
            />

            <div className="min-h-screen bg-background text-foreground">
                <section className="border-b border-border bg-linear-to-br from-indigo-600/10 via-background to-violet-600/10">
                    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                        <Breadcrumbs
                            items={[
                                { name: 'Blog', path: '/blog' },
                                { name: 'Authors', path: '/blog' },
                                { name: author.name, path: canonicalPath },
                            ]}
                        />
                        <Link
                            href="/blog"
                            className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground mb-5 mt-3"
                        >
                            <ChevronLeft className="h-3.5 w-3.5" /> All posts
                        </Link>

                        <div className="flex flex-wrap items-center gap-2 mb-4">
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-primary">
                                <User className="h-3 w-3" /> Author profile
                            </span>
                        </div>

                        <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            {author.name}
                        </h1>
                        <p className="mt-2 text-lg font-semibold text-primary">{author.credential}</p>
                        <p className="mt-2 text-sm font-medium text-muted-foreground">{author.role}</p>

                        <p className="mt-5 max-w-3xl text-base text-muted-foreground leading-relaxed">
                            {author.bio}
                        </p>

                        <div className="mt-5">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                                Expertise
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {author.expertise.map((e) => (
                                    <span key={e} className="blog-tag-chip">
                                        {e}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                </section>

                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h2 className="text-xl font-bold flex items-center gap-2 mb-5">
                        <GraduationCap className="h-5 w-5 text-primary" />
                        Posts by {author.name} ({posts.length})
                    </h2>
                    {posts.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
                            No posts yet. <Link href="/blog" className="text-primary hover:underline">Browse all posts →</Link>
                        </div>
                    ) : (
                        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                            {posts.map((p) => (
                                <BlogCard key={p.slug} post={p} />
                            ))}
                        </div>
                    )}

                    {reviewed.length > 0 ? (
                        <div className="mt-12">
                            <h2 className="text-xl font-bold flex items-center gap-2 mb-5">
                                <User className="h-5 w-5 text-primary" />
                                Medically reviewed by {author.name} ({reviewed.length})
                            </h2>
                            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                                {reviewed.map((p) => (
                                    <BlogCard key={p.slug} post={p} />
                                ))}
                            </div>
                        </div>
                    ) : null}
                </section>
            </div>
        </>
    );
}
