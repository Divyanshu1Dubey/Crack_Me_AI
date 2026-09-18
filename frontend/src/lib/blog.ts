import type { ReactNode } from 'react';

import cmsLast5Days from '@/content/blog/upsc-cms-last-5-days-strategy';
import cmsNeetPgLastWeek from '@/content/blog/cms-and-neet-pg-last-week-shared-revision';
import cms2026Notification from '@/content/blog/upsc-cms-2026-official-notification-guide';
import neetPgVsUpscCms from '@/content/blog/neet-pg-vs-upsc-cms';

// August 2026 SEO expansion — 6 new posts covering syllabus, cutoff,
// strategy, comparative decision content, and a verified book shortlist.
// Each post emits Article + FAQ + BreadcrumbList JSON-LD; see the
// `BlogPostLayout` for the schema wiring.
import cmsSyllabusHighYield from '@/content/blog/upsc-cms-syllabus-high-yield-topics';
import cmsCutoff2024 from '@/content/blog/upsc-cms-2024-cutoff-marks-category-wise';
import cmsPrepStrategy6Month from '@/content/blog/upsc-cms-preparation-strategy-6-month-plan';
import neetPgCutoff2024 from '@/content/blog/neet-pg-2024-cutoff-category-wise';
import neetPgPrepStrategy from '@/content/blog/neet-pg-preparation-strategy-study-plans';
import neetPgVsIniCet from '@/content/blog/neet-pg-vs-ini-cet';
import iniCetCutoff2024 from '@/content/blog/ini-cet-2024-cutoff-closing-ranks';
import cmsVsNeetPgVsIniCet from '@/content/blog/cms-vs-neet-pg-vs-ini-cet';
import bestPgBooks from '@/content/blog/best-pg-medical-entrance-books';

/**
 * EEAT-grade blog post shape.
 *
 * The shape was rebuilt specifically to support Google's March-2024 +
 * August-2024 core updates that reward experience + authoritativeness
 * + transparency. Each meaningful signal is captured explicitly:
 *
 *   - `authorId`     → resolves to an AuthorProfile and is emitted as a
 *                      `Person` JSON-LD node (with `knowsAbout[]`,
 *                      `worksFor`, `sameAs`) on every post.
 *   - `reviewedBy`   → a separate, named clinician reviewer with their
 *                      own Person block. Distinguishes writer from
 *                      reviewer — required for YMYL medical content.
 *   - `references`   → first-class source list rendered at the bottom
 *                      of every post and emitted as `citation[]` in the
 *                      Article JSON-LD.
 *   - `toc`          → ship an explicit Table of Contents; the post
 *                      layout renders it AND emits `speakable` for
 *                      Google Assistant + voice assistants.
 *   - `difficulty`   → "beginner" / "intermediate" / "advanced" → used
 *                      to filter, badge and summarise.
 *   - `revisionLog`  → appended to the bottom of every post so readers
 *                      can audit whether the content is fresh.
 *   - `updatedAt`    → distinct from `dateModified` — `updatedAt` is
 *                      editorial copy refresh; `dateModified` is the
 *                      last touched timestamp surfaced in JSON-LD.
 */
export interface BlogPost {
    /** URL slug, e.g. `upsc-cms-last-5-days-strategy` */
    slug: string;
    /** SEO title — used as `<title>` and `og:title`. Should be ≤ 60 chars
     *  to avoid Google truncation; the layout will append the site
     *  template automatically. */
    title: string;
    /** SEO description — used as meta description and `og:description`.
     *  Keep ≤ 160 chars. */
    description: string;
    /** Short excerpt — shown on cards + meta. ≤ 180 chars. */
    excerpt: string;
    /** Path to cover image under /public. Optional. */
    coverImage?: string;
    /** Primary category (used for /blog/category/<slug> hub pages). */
    category: string;
    /** Subcategory — used for the visual pill set in the hero. */
    subcategory?: string;
    /** Free-form tags shown as chips; power search + related-posts. */
    tags: string[];
    /** Difficulty — "beginner" | "intermediate" | "advanced" */
    difficulty: 'beginner' | 'intermediate' | 'advanced';
    /** Author slug (must exist in src/content/authors.ts). */
    authorId: string;
    /** Optional separate clinical reviewer. */
    reviewedBy?: string;
    /** Human-readable author byline (legacy field — derives from authorId). */
    author: string;
    /** Author role / credential. */
    authorRole: string;
    /** ISO date string. */
    datePublished: string;
    /** ISO date string — content refreshed on this date. */
    dateModified: string;
    /** ISO date string — last editorial copy refresh (drives "Updated on …"). */
    updatedAt: string;
    /** Human-readable reading time, e.g. "14 min". */
    readingTime: string;
    /** Word count (filled by build script — falls back to actual count
     *  of `body` if not set). */
    wordCount?: number;
    /** Inline CTA shown above the fold. Use helpful framing
     *  ("Practise 50 matched PYQs" — not "Sign up now!"). */
    primaryCta: {
        label: string;
        href: string;
        eventName?: string;
        eventParams?: Record<string, unknown>;
    };
    /** Related exam / topic paths surfaced as secondary CTAs. */
    relatedExamPaths?: string[];
    /** FAQ items — also emitted as FAQPage JSON-LD. */
    faqs: { q: string; a: string }[];
    /** Stable Table of Contents — headings the layout wires up to scroll-spy
     *  AND emits as `speakable[]` for Google Assistant. If empty, the
     *  layout auto-builds one from `body` h2s. */
    toc: { id: string; label: string }[];
    /** Medical / official references — rendered at the bottom of every
     *  post AND emitted as `citation[]` in Article JSON-LD. */
    references: { label: string; url?: string; published?: string }[];
    /** Revision log (oldest → newest). Surfaced in the post footer. */
    revisionLog?: { date: string; note: string }[];
    /** Full markdown body. */
    body: string;
    /** Optional React snippet shown at the very top of the post. */
    prelude?: ReactNode;
    /** Optional React snippet shown at the very bottom (after FAQ + CTA). */
    outro?: ReactNode;
    /** "Pinned" / "Trending" flags surfaced on the hub cards. */
    pinned?: boolean;
    trending?: boolean;
}

/** The single source of truth for blog posts. */
const posts: BlogPost[] = [
    // Original 4 posts.
    cms2026Notification,
    cmsLast5Days,
    cmsNeetPgLastWeek,
    neetPgVsUpscCms,
    // August 2026 expansion — 6 new posts.
    cmsSyllabusHighYield,
    cmsCutoff2024,
    cmsPrepStrategy6Month,
    neetPgCutoff2024,
    neetPgPrepStrategy,
    neetPgVsIniCet,
    iniCetCutoff2024,
    cmsVsNeetPgVsIniCet,
    bestPgBooks,
];

// Newest first.
posts.sort((a, b) => (a.datePublished < b.datePublished ? 1 : -1));

/** All posts, newest first. */
export function getAllPosts(): BlogPost[] {
    return posts;
}

/** Look up by slug, or undefined. */
export function getPostBySlug(slug: string): BlogPost | undefined {
    return posts.find((p) => p.slug === slug);
}

/** All post slugs — used by `generateStaticParams`. */
export function getAllPostSlugs(): string[] {
    return posts.map((p) => p.slug);
}

/** Up to N related posts that share ≥ 1 tag with the source post. */
export function getRelatedPosts(source: BlogPost, n = 2): BlogPost[] {
    const sourceTags = new Set(source.tags.map((t) => t.toLowerCase()));
    const scored = posts
        .filter((p) => p.slug !== source.slug)
        .map((p) => {
            const shared = p.tags.reduce((acc, t) => acc + (sourceTags.has(t.toLowerCase()) ? 1 : 0), 0);
            return { post: p, shared };
        })
        .filter((s) => s.shared > 0)
        .sort((a, b) => b.shared - a.shared);
    return scored.slice(0, n).map((s) => s.post);
}

/** All unique categories with at least one post. */
export function getAllCategories(): { name: string; slug: string; count: number }[] {
    const map = new Map<string, number>();
    posts.forEach((p) => map.set(p.category, (map.get(p.category) ?? 0) + 1));
    return Array.from(map.entries())
        .map(([name, count]) => ({
            name,
            slug: categoryToSlug(name),
            count,
        }))
        .sort((a, b) => b.count - a.count);
}

/** Posts in a category, newest first. */
export function getPostsByCategory(categorySlug: string): BlogPost[] {
    return posts.filter((p) => categoryToSlug(p.category) === categorySlug);
}

/** Posts with a given tag, newest first. */
export function getPostsByTag(tagSlug: string): BlogPost[] {
    const norm = tagSlug.toLowerCase().replace(/-/g, ' ');
    return posts.filter((p) =>
        p.tags.some((t) => t.toLowerCase() === norm),
    );
}

/** All unique tags with their counts. */
export function getAllTags(): { name: string; slug: string; count: number }[] {
    const map = new Map<string, number>();
    posts.forEach((p) =>
        p.tags.forEach((t) => map.set(t, (map.get(t) ?? 0) + 1)),
    );
    return Array.from(map.entries())
        .map(([name, count]) => ({
            name,
            slug: tagToSlug(name),
            count,
        }))
        .sort((a, b) => b.count - a.count);
}

/** Turn a category or tag display name into a URL-safe slug. */
export function categoryToSlug(name: string): string {
    return name
        .toLowerCase()
        .replace(/&/g, 'and')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '');
}

/** Tags have a stricter transform — drop leading "and " etc. */
export function tagToSlug(name: string): string {
    return categoryToSlug(name);
}

/** Find the top `n` trending posts (pinned first, then newest). */
export function getFeaturedPosts(n = 4): BlogPost[] {
    const pinned = posts.filter((p) => p.pinned);
    const rest = posts.filter((p) => !p.pinned).slice(0, Math.max(0, n - pinned.length));
    return [...pinned, ...rest].slice(0, n);
}

/** Approximate word count of a markdown body. */
export function countWords(markdown: string): number {
    return markdown
        .replace(/```[\s\S]*?```/g, ' ')
        .replace(/[#>*_`~|\[\]]/g, ' ')
        .split(/\s+/)
        .filter(Boolean).length;
}

/** Human-readable date in long form, e.g. "28 July 2026". */
export function formatPostDate(iso: string): string {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' });
}

/** Slugify a heading into an anchor id. */
export function slugifyHeading(text: string): string {
    return text
        .toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-')
        .slice(0, 80);
}

/** Auto-build a Table of Contents from a markdown body
 *  (h2 / h3 only). Returns stable ids so anchors survive SSG. */
export function buildAutoToc(markdown: string): { id: string; label: string; level: 2 | 3 }[] {
    const lines = markdown.split(/\r?\n/);
    const out: { id: string; label: string; level: 2 | 3 }[] = [];
    let inCode = false;
    for (const line of lines) {
        if (line.startsWith('```')) { inCode = !inCode; continue; }
        if (inCode) continue;
        const m = /^(#{2,3})\s+(.+?)\s*$/.exec(line);
        if (!m) continue;
        const level = m[1].length as 2 | 3;
        const label = m[2].replace(/[`*_]/g, '').trim();
        out.push({ id: slugifyHeading(label), label, level });
    }
    return out;
}
