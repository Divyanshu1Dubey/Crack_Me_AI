import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { ArrowRight, BookOpen, Sparkles } from 'lucide-react';
import { BlogCard } from '@/components/BlogCard';
import { TrackedLink } from '@/components/TrackedLink';
import { buildPageMetadata } from '@/lib/metadata';
import { getAllPosts } from '@/lib/blog';
import { siteUrl } from '@/lib/seo';

export const metadata: Metadata = buildPageMetadata({
    title: 'CrackCMS Blog — UPSC CMS, NEET PG & Medical PG Exam Strategy',
    description:
        'High-yield exam strategies, last-day revision plans, mock-test scoring tactics and answer-writing guides for UPSC CMS, NEET PG, INI-CET and FMGE aspirants.',
    path: '/blog',
    image: '/cms-circle-logo.png',
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

export default function BlogIndexPage() {
    const posts = getAllPosts();
    const [featured, ...rest] = posts;

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
        blogPost: posts.map((p) => ({
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
            <Script
                id="blog-index-schema"
                type="application/ld+json"
                strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
            />

            <div className="min-h-screen bg-background text-foreground">
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
                            Written by the CrackCMS editorial team, reviewed by clinicians, grounded in{' '}
                            <strong className="text-foreground">3,300+ PYQs</strong> and real candidate data.
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
                        <div className="grid gap-6 lg:grid-cols-12">
                            <div className="lg:col-span-8">
                                <BlogCard post={featured} featured />
                            </div>
                            <aside className="lg:col-span-4 space-y-4">
                                {rest.map((p) => (
                                    <BlogCard key={p.slug} post={p} />
                                ))}
                            </aside>
                        </div>
                    ) : null}

                    {posts.length === 0 && (
                        <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
                            No posts yet. Check back soon.
                        </div>
                    )}

                    <div className="mt-12 rounded-2xl border border-border bg-linear-to-br from-primary/10 via-accent/20 to-teal-500/10 p-6 sm:p-8 text-center">
                        <h3 className="text-lg font-bold">Practise the PYQs behind every strategy.</h3>
                        <p className="mt-2 text-sm text-muted-foreground">
                            Every tactic in every post links back to the original previous-year question.
                            Browse 3,300+ PYQs across UPSC CMS, NEET PG and INI-CET — free, no sign-up wall.
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
                            Free to use. Optional account if you want your progress saved.
                        </p>
                    </div>
                </section>
            </div>
        </>
    );
}
