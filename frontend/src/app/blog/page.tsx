import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight, BookOpen, Sparkles } from 'lucide-react';
import { BlogCard } from '@/components/BlogCard';
import { TrackedLink } from '@/components/TrackedLink';
import { buildPageMetadata, jsonLdString } from '@/lib/metadata';
import { categoriesOf, loadBlogCatalog } from '@/lib/blog';
import { siteUrl } from '@/lib/seo';
import { CMS_PYQ_COUNT } from '@/lib/bankStats';
import Breadcrumbs from '@/components/Breadcrumbs';

export const metadata: Metadata = buildPageMetadata({
    title: 'CrackCMS Blog — UPSC CMS, NEET PG & Medical PG Exam Strategy',
    description:
        'High-yield exam strategies, last-day revision plans, mock-test scoring tactics and answer-writing guides for UPSC CMS, NEET PG, INI-CET and FMGE aspirants.',
    path: '/blog',
    type: 'website',
    keywords: [
        'UPSC CMS blog',
        'NEET PG blog',
        'medical exam strategy',
        'last 5 days CMS',
        'last week NEET PG',
        'CMS mock test tips',
        'NEET PG revision plan',
        'medical PG preparation blog',
        'CMS last minute tips',
    ],
});

// The hub shows the newest posts and links every category; the full list
// lives on the category pages (it used to render all 130 posts in a sidebar,
// a ~700 KB page).
const LATEST_POSTS = 9;
const JSON_LD_POSTS = 20;
/** Posts shown beside the featured one; the rest go in the grid below. */
const ASIDE_POSTS = 3;

// The published posts in the database (edited at /admin/blog), regenerated at
// most every 5 minutes (BLOG_REVALIDATE_SECONDS).
export const revalidate = 300;

export default async function BlogIndexPage() {
    const posts = await loadBlogCatalog();
    const [featured, ...others] = posts;
    const rest = others.slice(0, LATEST_POSTS - 1);
    const categories = categoriesOf(posts);

    const jsonLd = {
        '@context': 'https://schema.org',
        '@type': 'Blog',
        name: 'CrackCMS Blog',
        description:
            'High-yield exam strategies for UPSC CMS, NEET PG, INI-CET and FMGE aspirants.',
        url: `${siteUrl}/blog`,
        publisher: {
            '@type': 'Organization',
            name: 'CrackCMS',
            url: siteUrl,
            logo: { '@type': 'ImageObject', url: `${siteUrl}/cms-circle-logo.png` },
        },
        blogPost: posts.slice(0, JSON_LD_POSTS).map((p) => ({
            '@type': 'BlogPosting',
            headline: p.title,
            url: `${siteUrl}/blog/${p.slug}`,
            datePublished: p.datePublished,
            dateModified: p.dateModified,
            author: { '@type': 'Person', name: p.author },
            // Use the per-post dynamic OG image endpoint so Google Discover /
            // rich-results pull a real 1200×630 preview instead of falling
            // back to the generic logo.
            image: `${siteUrl}/blog/${p.slug}/opengraph-image`,
        })),
    };

    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }} />

            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-6xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'Blog', path: '/blog' }]} />
                </div>
                {/* Hub hero */}
                <section className="border-b border-border bg-linear-to-br from-indigo-600/10 via-background to-violet-600/10">
                    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
                        <div className="flex flex-wrap items-center gap-2 mb-4">
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-primary">
                                <BookOpen className="h-3 w-3" /> The CrackCMS Blog
                            </span>
                        </div>
                        <h1 className="text-4xl font-black tracking-tight sm:text-5xl md:text-6xl">
                            Exam strategies, not fluff.
                        </h1>
                        <p className="mt-5 max-w-3xl text-lg text-muted-foreground">
                            What actually works in the last 5 days before UPSC CMS, NEET PG, INI-CET and FMGE.
                            Written by the CrackCMS editorial team and grounded in{' '}
                            <strong className="text-foreground">{CMS_PYQ_COUNT} UPSC CMS PYQs</strong> and the NEET PG question bank.
                        </p>
                        <div className="mt-7 flex flex-wrap items-center gap-2">
                            <TrackedLink
                                href="/cms"
                                eventName="blog_hub_click"
                                eventParams={{ source: 'blog_index', target: 'cms_microsite' }}
                                className="rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-95"
                            >
                                Explore UPSC CMS prep
                            </TrackedLink>
                            <TrackedLink
                                href="/neet-pg"
                                eventName="blog_hub_click"
                                eventParams={{ source: 'blog_index', target: 'neet_pg_microsite' }}
                                className="rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground hover:bg-muted"
                            >
                                Explore NEET PG prep
                            </TrackedLink>
                            <Link
                                href="/questions"
                                className="rounded-xl px-5 py-2.5 text-sm font-bold text-muted-foreground hover:text-foreground"
                            >
                                Practise PYQs →
                            </Link>
                        </div>
                    </div>
                </section>

                {/* Featured + grid */}
                <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
                    {featured ? (
                        <div className="mb-10 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                            <Sparkles className="h-4 w-4 text-primary" /> Latest strategy
                        </div>
                    ) : null}

                    {featured ? (
                        <>
                            {/* Featured post + the next few beside it. The aside is a
                                grid so every card is its own block (space-y on inline
                                card links let them run together). */}
                            <div className="grid gap-6 lg:grid-cols-12">
                                <div className="lg:col-span-8">
                                    <BlogCard post={featured} featured />
                                </div>
                                <aside className="lg:col-span-4 grid content-start gap-4">
                                    {rest.slice(0, ASIDE_POSTS).map((p) => (
                                        <BlogCard key={p.slug} post={p} />
                                    ))}
                                </aside>
                            </div>
                            {/* Everything else uses the full width instead of one long
                                narrow column next to an empty two-thirds of the page. */}
                            {rest.length > ASIDE_POSTS && (
                                <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                                    {rest.slice(ASIDE_POSTS).map((p) => (
                                        <BlogCard key={p.slug} post={p} />
                                    ))}
                                </div>
                            )}
                        </>
                    ) : null}

                    {categories.length > 0 && (
                        <nav aria-label="Blog categories" className="mt-12">
                            <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-3">
                                Browse all {posts.length} posts by category
                            </h2>
                            <div className="flex flex-wrap gap-2">
                                {categories.map((c) => (
                                    <Link
                                        key={c.slug}
                                        href={`/blog/category/${c.slug}`}
                                        className="rounded-full border border-border bg-card px-3 py-1.5 text-xs font-bold text-foreground hover:border-primary hover:text-primary transition-colors"
                                    >
                                        {c.name} ({c.count})
                                    </Link>
                                ))}
                            </div>
                        </nav>
                    )}

                    {posts.length === 0 && (
                        <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
                            No posts yet. Check back soon.
                        </div>
                    )}

                    <div className="mt-12 rounded-2xl border border-border bg-linear-to-br from-primary/10 via-accent/20 to-teal-500/10 p-6 sm:p-8 text-center">
                        <h3 className="text-lg font-bold">Practise the PYQs behind every strategy.</h3>
                        <p className="mt-2 text-sm text-muted-foreground">
                            Every tactic in every post links back to the original previous-year question.
                            Practise {CMS_PYQ_COUNT} UPSC CMS PYQs and the NEET PG bank with a free account.
                        </p>
                        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                            <Link
                                href="/questions"
                                className="rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-95"
                            >
                                Browse the question bank
                            </Link>
                            <Link
                                href="/simulator"
                                className="rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground hover:bg-muted"
                            >
                                Try a mock simulator <ArrowRight className="inline h-4 w-4 ml-1" />
                            </Link>
                        </div>
                        <p className="mt-3 text-[11px] text-muted-foreground">
                            Free account; premium plans unlock the full bank and mock tests.
                        </p>
                    </div>
                </section>
            </div>
        </>
    );
}
