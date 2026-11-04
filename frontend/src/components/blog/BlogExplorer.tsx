'use client';

import Link from 'next/link';
import { useDeferredValue, useMemo, useState } from 'react';
import { ArrowRight, Search, X } from 'lucide-react';
import { BlogCard } from '@/components/BlogCard';
import type { BlogCardData } from '@/lib/blog';

interface BlogExplorerProps {
    /** Every published post, newest first. */
    posts: BlogCardData[];
    categories: { name: string; slug: string; count: number }[];
    /** Shown in the featured row above: left out of the grid while nothing is filtered. */
    featuredSlugs?: string[];
    pageSize?: number;
}

const fold = (value: string) => value.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();

/**
 * "All posts" on /blog: every published post is reachable from the index —
 * search (title, excerpt, category, tags), category chips and "Show more".
 * The first page is server-rendered; the category pages stay the crawlable,
 * complete lists.
 */
export default function BlogExplorer({ posts, categories, featuredSlugs = [], pageSize = 12 }: BlogExplorerProps) {
    const [query, setQuery] = useState('');
    const [category, setCategory] = useState('');
    const [limit, setLimit] = useState(pageSize);
    const deferredQuery = useDeferredValue(query);

    const index = useMemo(
        () => posts.map((post) => ({ post, text: fold([post.title, post.excerpt, post.category, ...post.tags].join(' ')) })),
        [posts],
    );
    const terms = fold(deferredQuery).split(/\s+/).filter(Boolean);
    const filtering = terms.length > 0 || category !== '';
    const featured = new Set(featuredSlugs);
    const matches = index
        .filter(({ post, text }) => (category ? post.category === category : true)
            && terms.every((term) => text.includes(term))
            && (filtering || !featured.has(post.slug)))
        .map(({ post }) => post);
    const shown = matches.slice(0, limit);
    const selected = categories.find((c) => c.name === category);

    const choose = (name: string) => {
        setCategory((current) => (current === name ? '' : name));
        setLimit(pageSize);
    };

    return (
        <div>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <label className="relative block w-full lg:max-w-sm">
                    <span className="sr-only">Search the blog</span>
                    <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                    <input
                        type="search"
                        value={query}
                        onChange={(e) => { setQuery(e.target.value); setLimit(pageSize); }}
                        placeholder="Search posts, e.g. ECG, cutoff, PSM"
                        className="h-11 w-full rounded-xl border border-border bg-card pl-10 pr-10 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                    {query ? (
                        <button type="button" onClick={() => setQuery('')} aria-label="Clear the search"
                            className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground">
                            <X className="h-4 w-4" />
                        </button>
                    ) : null}
                </label>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by category">
                    <button type="button" aria-pressed={category === ''} onClick={() => choose('')}
                        className={chipClass(category === '')}>
                        All <span className="opacity-70">{posts.length}</span>
                    </button>
                    {categories.map((c) => (
                        <button key={c.slug} type="button" aria-pressed={category === c.name} onClick={() => choose(c.name)}
                            className={chipClass(category === c.name)}>
                            {c.name} <span className="opacity-70">{c.count}</span>
                        </button>
                    ))}
                </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                <p role="status" aria-live="polite">
                    {matches.length === 0
                        ? 'No posts match.'
                        : `Showing ${shown.length} of ${matches.length} ${matches.length === 1 ? 'post' : 'posts'}${filtering ? '' : ' (newest first)'}`}
                </p>
                {selected ? (
                    <Link href={`/blog/category/${selected.slug}`} className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
                        Open the {selected.name} page <ArrowRight className="h-4 w-4" />
                    </Link>
                ) : null}
            </div>

            {matches.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
                    Nothing matches “{deferredQuery.trim() || category}”.{' '}
                    <button type="button" className="font-semibold text-primary hover:underline" onClick={() => { setQuery(''); setCategory(''); }}>
                        Show every post
                    </button>
                </div>
            ) : (
                <ul className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {shown.map((post) => (
                        <li key={post.slug} className="min-w-0">
                            <BlogCard post={post} />
                        </li>
                    ))}
                </ul>
            )}

            {shown.length < matches.length ? (
                <div className="mt-8 flex justify-center">
                    <button type="button" onClick={() => setLimit((n) => n + pageSize)}
                        className="rounded-xl border border-border bg-card px-6 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-primary hover:text-primary">
                        Show more posts ({matches.length - shown.length} left)
                    </button>
                </div>
            ) : null}
        </div>
    );
}

function chipClass(active: boolean): string {
    return `inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-bold transition-colors ${
        active
            ? 'border-primary bg-primary text-primary-foreground'
            : 'border-border bg-card text-foreground hover:border-primary hover:text-primary'
    }`;
}
