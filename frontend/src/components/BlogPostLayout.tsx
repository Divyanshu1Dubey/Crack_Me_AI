import Link from 'next/link';
import {
    ArrowLeft,
    BookOpen,
    CalendarDays,
    CheckCircle2,
    Clock,
    GraduationCap,
    ListTree,
    MessageCircle,
    Share2,
    Twitter,
    User,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrackedLink } from '@/components/TrackedLink';
import { FormattedText } from '@/components/FormattedText';
import { CopyLinkButton } from '@/components/CopyLinkButton';
import FAQSection from '@/components/FAQSection';
import Breadcrumbs from '@/components/Breadcrumbs';
import StructuredData from '@/components/StructuredData';
import { CommentsGiscus } from '@/components/CommentsGiscus';
import {
    articleSchema,
    breadcrumbSchema,
    faqSchema,
    graphSchema,
    personSchema,
} from '@/lib/metadata';
import { siteName, siteUrl } from '@/lib/seo';
import type { BlogPost } from '@/lib/blog';
import { formatPostDate, getRelatedPosts } from '@/lib/blog';
import { getAuthor } from '@/content/authors';

interface BlogPostLayoutProps {
    post: BlogPost;
}

/** Difficulty is read from the post and rendered as a small badge. */
function difficultyLabel(d?: BlogPost['difficulty']) {
    if (d === 'beginner') return 'Beginner';
    if (d === 'advanced') return 'Advanced';
    return 'Intermediate';
}

function difficultyColor(d?: BlogPost['difficulty']) {
    if (d === 'beginner') return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30';
    if (d === 'advanced') return 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/30';
    return 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30';
}

/**
 * Decide whether a post should be emitted as a `MedicalWebPage` JSON-LD
 * (preferred for YMYL medical content) or a plain `Article`. We promote
 * to `MedicalWebPage` whenever the post has medical references — i.e.
 * when the editorial team has explicitly grounded clinical claims.
 */
function shouldEmitMedicalWebPage(post: BlogPost): boolean {
    return post.references.length > 0;
}

/**
 * Renders a single blog post — gradient hero, cover image, tag chips,
 * author byline, share row, sticky in-post CTA, body via `<FormattedText>`,
 * FAQ accordion, related posts, and Giscus comments.
 *
 * EEAT signals emitted:
 *   • Article (or MedicalWebPage) JSON-LD with citation[] + reviewedBy
 *   • Person JSON-LD for author + clinical reviewer
 *   • speakable[] xpaths for voice assistants
 *   • Visible "Medically reviewed by …" badge in the byline
 *   • References section rendered at the bottom + revision log
 *   • Author profile link to `/blog/author/<slug>` (when archive exists)
 */
export function BlogPostLayout({ post }: BlogPostLayoutProps) {
    const canonical = `/blog/${post.slug}`;
    const related = getRelatedPosts(post, 2);
    const author = getAuthor(post.authorId);
    const reviewer = post.reviewedBy ? getAuthor(post.reviewedBy) : null;
    const medicalPage = shouldEmitMedicalWebPage(post);

    const jsonLd = graphSchema([
        articleSchema({
            headline: post.title,
            description: post.description,
            path: canonical,
            datePublished: post.datePublished,
            dateModified: post.dateModified,
            authorName: author.name,
            authorUrl: `${siteUrl}/blog/author/${author.slug}`,
            reviewedByName: reviewer?.name,
            reviewedByCredential: reviewer?.credential,
            citations: post.references,
            speakable: ['#start-reading .blog-article h2:first-of-type', '.blog-excerpt'],
            medicalPageType: medicalPage,
            image: post.coverImage,
        }),
        personSchema({
            name: author.name,
            credential: author.credential,
            role: author.role,
            bio: author.bio,
            expertise: author.expertise,
            sameAs: author.sameAs,
            url: `${siteUrl}/blog/author/${author.slug}`,
        }),
        ...(post.faqs.length > 0 ? [faqSchema(post.faqs)] : []),
        breadcrumbSchema([
            { name: 'Home', path: '/' },
            { name: 'Blog', path: '/blog' },
            { name: post.category, path: '/blog' },
            { name: post.title, path: canonical },
        ]),
    ]);

    const shareUrl = `${siteUrl}${canonical}`;
    const twitterShare = `https://twitter.com/intent/tweet?text=${encodeURIComponent(post.title)}&url=${encodeURIComponent(shareUrl)}`;
    const whatsappShare = `https://wa.me/?text=${encodeURIComponent(`${post.title} — ${shareUrl}`)}`;

    const updatedISO = post.updatedAt ?? post.dateModified;
    const tocItems = post.toc?.length
        ? post.toc
        : post.body
            ? extractH2sFromMarkdown(post.body)
            : [];

    return (
        <>
            <StructuredData id={`blog-schema-${post.slug}`} data={jsonLd} />

            <div className="min-h-screen bg-background text-foreground">
                {/* Hero */}
                <section className="blog-hero border-b border-border">
                    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                        <Breadcrumbs
                            items={[
                                { name: 'Blog', path: '/blog' },
                                { name: post.category, path: '/blog' },
                                { name: post.title, path: canonical },
                            ]}
                        />
                        <Link
                            href="/blog"
                            className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground mb-5 mt-3"
                        >
                            <ArrowLeft className="h-3.5 w-3.5" /> All posts
                        </Link>

                        <div className="flex flex-wrap items-center gap-2 mb-4">
                            <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                                <BookOpen className="h-3 w-3 mr-1" /> {post.category}
                            </Badge>
                            {post.subcategory ? (
                                <Badge variant="secondary" className="text-xs font-semibold uppercase tracking-wider">
                                    {post.subcategory}
                                </Badge>
                            ) : null}
                            <span
                                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${difficultyColor(post.difficulty)}`}
                            >
                                {difficultyLabel(post.difficulty)}
                            </span>
                            {post.tags.slice(0, 4).map((tag) => (
                                <span key={tag} className="blog-tag-chip">
                                    #{tag.replace(/\s+/g, '')}
                                </span>
                            ))}
                        </div>

                        <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl lg:text-5xl">
                            {post.title}
                        </h1>
                        <p className="blog-excerpt mt-5 text-lg text-muted-foreground max-w-3xl">
                            {post.excerpt}
                        </p>

                        <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
                            <span className="inline-flex items-center gap-1.5">
                                <User className="h-3.5 w-3.5" /> By{' '}
                                <Link
                                    href={`/blog/author/${author.slug}`}
                                    className="text-foreground font-semibold hover:underline"
                                >
                                    {author.name}
                                </Link>
                                <span className="text-muted-foreground/80">· {author.credential}</span>
                            </span>
                            {reviewer ? (
                                <span className="inline-flex items-center gap-1.5">
                                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                                    Medically reviewed by{' '}
                                    <strong className="text-foreground">{reviewer.name}</strong>
                                </span>
                            ) : null}
                            <span className="inline-flex items-center gap-1.5">
                                <CalendarDays className="h-3.5 w-3.5" /> Updated{' '}
                                <strong className="text-foreground">{formatPostDate(updatedISO)}</strong>
                            </span>
                            <span className="inline-flex items-center gap-1.5">
                                <Clock className="h-3.5 w-3.5" />{' '}
                                <strong className="text-foreground">{post.readingTime}</strong> read
                            </span>
                        </div>

                        {/* Inline CTA strip — above the fold (help-first, never sales-y) */}
                        <div className="mt-7 flex flex-wrap items-center gap-2">
                            <TrackedLink
                                href={post.primaryCta.href}
                                eventName={post.primaryCta.eventName ?? 'blog_practice_intent'}
                                eventParams={post.primaryCta.eventParams ?? { source: 'blog', surface: 'hero' }}
                                className="rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-95"
                            >
                                {post.primaryCta.label}
                            </TrackedLink>
                            <Link
                                href="#start-reading"
                                className="rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground hover:bg-muted"
                            >
                                Start reading
                            </Link>
                        </div>
                    </div>
                </section>

                {/* Body + sidebar */}
                <article id="start-reading" className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
                    <div className="grid gap-10 lg:grid-cols-12">
                        {/* Body */}
                        <div className="lg:col-span-8 min-w-0">
                            <div className="blog-article">
                                <FormattedText text={post.body} />
                            </div>

                            {/* Share row */}
                            <div className="mt-10 flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-card p-4 sm:p-5">
                                <span className="inline-flex items-center gap-2 text-xs font-bold text-foreground">
                                    <Share2 className="h-4 w-4" /> Share this post
                                </span>
                                <a
                                    href={twitterShare}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="blog-share-btn"
                                    aria-label="Share on Twitter"
                                >
                                    <Twitter className="h-3.5 w-3.5" /> Twitter / X
                                </a>
                                <a
                                    href={whatsappShare}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="blog-share-btn"
                                    aria-label="Share on WhatsApp"
                                >
                                    <MessageCircle className="h-3.5 w-3.5" /> WhatsApp
                                </a>
                                <CopyLinkButton url={shareUrl} />
                            </div>

                            {/* References */}
                            {post.references.length > 0 ? (
                                <section className="mt-12 rounded-2xl border border-border bg-card p-5 sm:p-6">
                                    <h2 className="text-lg font-bold flex items-center gap-2 mb-3">
                                        <BookOpen className="h-5 w-5 text-primary" />
                                        References & further reading
                                    </h2>
                                    <p className="text-xs text-muted-foreground mb-4">
                                        Every clinical claim in this article is anchored to a primary source.
                                        Click through to verify, and use the same habit in your revision.
                                    </p>
                                    <ol className="space-y-2 text-sm">
                                        {post.references.map((ref, i) => (
                                            <li key={`${ref.label}-${i}`} className="leading-relaxed">
                                                <span className="mr-2 font-bold text-muted-foreground">{i + 1}.</span>
                                                {ref.url ? (
                                                    <a
                                                        href={ref.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-primary hover:underline"
                                                    >
                                                        {ref.label}
                                                    </a>
                                                ) : (
                                                    <span>{ref.label}</span>
                                                )}
                                            </li>
                                        ))}
                                    </ol>
                                </section>
                            ) : null}

                            {/* Revision log */}
                            {post.revisionLog && post.revisionLog.length > 0 ? (
                                <section className="mt-6 rounded-2xl border border-border bg-card p-5 sm:p-6">
                                    <h2 className="text-base font-bold flex items-center gap-2 mb-3">
                                        <CalendarDays className="h-4 w-4 text-primary" />
                                        Revision history
                                    </h2>
                                    <ul className="space-y-2 text-xs text-muted-foreground">
                                        {post.revisionLog.map((entry, i) => (
                                            <li key={`${entry.date}-${i}`} className="leading-relaxed">
                                                <strong className="text-foreground font-semibold">
                                                    {formatPostDate(entry.date)} —
                                                </strong>{' '}
                                                {entry.note}
                                            </li>
                                        ))}
                                    </ul>
                                </section>
                            ) : null}

                            {/* FAQs */}
                            {post.faqs.length > 0 ? (
                                <div className="mt-10">
                                    <h2 className="text-xl font-bold flex items-center gap-2 mb-4">
                                        <GraduationCap className="h-5 w-5 text-primary" />
                                        Frequently asked questions
                                    </h2>
                                    <FAQSection items={post.faqs} showIcon={false} title="" />
                                </div>
                            ) : null}

                            {/* Related posts */}
                            {related.length > 0 ? (
                                <section className="mt-12">
                                    <h2 className="text-xl font-bold mb-4">Related reading</h2>
                                    <div className="grid gap-4 sm:grid-cols-2">
                                        {related.map((r) => (
                                            <Link
                                                key={r.slug}
                                                href={`/blog/${r.slug}`}
                                                className="blog-related-card"
                                            >
                                                <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-wider">
                                                    {r.category}
                                                </Badge>
                                                <h3 className="mt-2 text-base font-bold text-foreground">{r.title}</h3>
                                                <p className="mt-1 text-xs text-muted-foreground">{r.readingTime} read</p>
                                            </Link>
                                        ))}
                                    </div>
                                </section>
                            ) : null}

                            {/* Bottom CTA (help-first, never sales-y) */}
                            <Card className="mt-12 border-primary/30 bg-linear-to-br from-primary/10 via-accent/20 to-teal-500/10">
                                <CardContent className="p-6 sm:p-8 text-center">
                                    <h3 className="text-lg font-bold">Hand this plan to your study group.</h3>
                                    <p className="mt-2 text-sm text-muted-foreground">
                                        CrackCMS is a free study desk for medical PG aspirants — 3,300+ PYQs,
                                        full mock simulators, spaced-repetition flashcards and an AI tutor
                                        that compares stem formats across UPSC CMS and NEET PG.
                                    </p>
                                    <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                                        <TrackedLink
                                            href={post.primaryCta.href}
                                            eventName={post.primaryCta.eventName ?? 'blog_practice_intent'}
                                            eventParams={{
                                                ...(post.primaryCta.eventParams ?? { source: 'blog' }),
                                                surface: 'bottom_cta',
                                            }}
                                            className="rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-95"
                                        >
                                            {post.primaryCta.label}
                                        </TrackedLink>
                                        <Link
                                            href="/questions"
                                            className="rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground hover:bg-muted"
                                        >
                                            Browse question bank
                                        </Link>
                                    </div>
                                    <p className="mt-3 text-[11px] text-muted-foreground">
                                        {siteName} by CrackLabs AI · <Link href="/editorial-policy" className="hover:text-foreground underline">Editorial policy</Link> · <Link href="/medical-review-policy" className="hover:text-foreground underline">Medical review policy</Link>
                                    </p>
                                </CardContent>
                            </Card>

                            {/* Comments */}
                            <section className="mt-12">
                                <h2 className="text-xl font-bold flex items-center gap-2 mb-4">
                                    <MessageCircle className="h-5 w-5 text-primary" /> Join the discussion
                                </h2>
                                <CommentsGiscus slug={post.slug} />
                            </section>
                        </div>

                        {/* Sidebar — TOC + author + contact */}
                        <aside className="lg:col-span-4">
                            <div className="lg:sticky lg:top-6 space-y-5">
                                {tocItems.length > 0 ? (
                                    <nav
                                        aria-label="Table of contents"
                                        className="rounded-2xl border border-border bg-card p-5"
                                    >
                                        <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-3">
                                            <ListTree className="h-4 w-4" /> On this page
                                        </h2>
                                        <ol className="space-y-1.5 text-sm">
                                            {tocItems.map((item, i) => (
                                                <li key={item.id}>
                                                    <a
                                                        href={`#${item.id}`}
                                                        className="text-foreground/80 hover:text-primary transition-colors"
                                                    >
                                                        <span className="text-muted-foreground mr-2">{i + 1}.</span>
                                                        {item.label}
                                                    </a>
                                                </li>
                                            ))}
                                        </ol>
                                    </nav>
                                ) : null}

                                <div className="rounded-2xl border border-border bg-card p-5">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">
                                        About the author
                                    </h2>
                                    <p className="text-sm font-semibold text-foreground">{author.name}</p>
                                    <p className="text-xs text-muted-foreground">{author.credential}</p>
                                    <p className="mt-3 text-xs text-muted-foreground leading-relaxed">{author.bio}</p>
                                    <Link
                                        href={`/blog/author/${author.slug}`}
                                        className="mt-3 inline-flex items-center text-xs font-bold text-primary hover:underline"
                                    >
                                        More from this author →
                                    </Link>
                                </div>

                                {reviewer && reviewer.slug !== author.slug ? (
                                    <div className="rounded-2xl border border-border bg-card p-5">
                                        <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">
                                            Medically reviewed by
                                        </h2>
                                        <p className="text-sm font-semibold text-foreground">{reviewer.name}</p>
                                        <p className="text-xs text-muted-foreground">{reviewer.credential}</p>
                                        <p className="mt-3 text-xs text-muted-foreground leading-relaxed">{reviewer.bio}</p>
                                    </div>
                                ) : null}

                                <div className="rounded-2xl border border-border bg-card p-5">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">
                                        Need help this week?
                                    </h2>
                                    <p className="text-xs text-muted-foreground leading-relaxed">
                                        Stuck on a specific PYQ at 2 AM? Drop it into the AI tutor — it
                                        works across both UPSC CMS and NEET PG stems, for free.
                                    </p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                        <Link
                                            href="/ai-tutor"
                                            className="rounded-xl bg-primary px-3 py-2 text-[11px] font-bold text-primary-foreground hover:opacity-95"
                                        >
                                            Open AI tutor
                                        </Link>
                                        <a
                                            href={`https://wa.me/919601981524?text=${encodeURIComponent('Hi CrackCMS team — I have a question about a PYQ.')}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="rounded-xl border border-border bg-card px-3 py-2 text-[11px] font-bold text-foreground hover:bg-muted"
                                        >
                                            WhatsApp us
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </aside>
                    </div>
                </article>
            </div>
        </>
    );
}

/**
 * Local fallback — build a minimal TOC from h2 headings in the markdown
 * body. We only use this when the post hasn't explicitly supplied a
 * pre-built `toc[]` (keeps older posts rendering without edit).
 */
function extractH2sFromMarkdown(markdown: string): { id: string; label: string }[] {
    const out: { id: string; label: string }[] = [];
    let inCode = false;
    for (const line of markdown.split(/\r?\n/)) {
        if (line.startsWith('```')) {
            inCode = !inCode;
            continue;
        }
        if (inCode) continue;
        const m = /^##\s+(.+?)\s*$/.exec(line);
        if (!m) continue;
        const label = m[1].replace(/[`*_]/g, '').trim();
        const id = label
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .trim()
            .replace(/\s+/g, '-')
            .slice(0, 80);
        out.push({ id, label });
    }
    return out;
}
