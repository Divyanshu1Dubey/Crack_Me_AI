'use client';

import Link from 'next/link';
import { Pencil } from 'lucide-react';
import { blogApiOrigin, type BlogPostAdmin } from '@/lib/blogAPI';
import { countBlogWords, formatPostDate, readingTimeLabel } from '@/lib/blogText';
import { BlogArticle } from './BlogArticle';

/** An unpublished post as its page will look (admins only; see DraftPreview). */
export default function DraftArticle({ post }: { post: BlogPostAdmin }) {
    const words = countBlogWords(post.body);
    return (
        <div className="min-h-screen bg-background text-foreground">
            <div className="border-b border-amber-500/40 bg-amber-500/10">
                <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm sm:px-6">
                    <p className="font-semibold text-amber-900 dark:text-amber-200">
                        {post.is_published ? 'Admin view of this post.' : 'Draft preview: only admins can see this page until the post is published.'}
                    </p>
                    <Link href={`/admin/blog?edit=${encodeURIComponent(post.slug)}`}
                        className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary hover:bg-primary/15">
                        <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> Edit post
                    </Link>
                </div>
            </div>
            <section className="blog-hero border-b border-border">
                <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <p className="text-xs font-bold uppercase tracking-wider text-primary">{post.category}</p>
                    <h1 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">{post.title}</h1>
                    {post.excerpt ? <p className="mt-5 max-w-3xl text-lg text-muted-foreground">{post.excerpt}</p> : null}
                    <p className="mt-6 text-xs text-muted-foreground">
                        {post.author} · {formatPostDate(post.updated_at || post.date_modified || post.date_published)} · {readingTimeLabel(words)} read
                    </p>
                </div>
            </section>
            <article className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
                <div className="lg:w-2/3">
                    {post.body.trim()
                        ? <BlogArticle markdown={post.body} preferredIds={post.toc} imageOrigin={blogApiOrigin()} />
                        : <p className="text-muted-foreground">This draft has no body yet.</p>}
                </div>
            </article>
        </div>
    );
}
