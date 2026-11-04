import Link from 'next/link';
import { ArrowRight, BookOpen, Clock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { BlogCardData } from '@/lib/blog';
import { formatPostDate } from '@/lib/blogText';

interface BlogCardProps {
    post: BlogCardData;
    featured?: boolean;
}

/**
 * Card for the /blog index, category, tag and author pages (and the client
 * explorer on /blog, so it takes plain BlogCardData and imports only
 * lib/blogText). Cards are full-height flex columns: in a grid row they line
 * up, with the date and reading time on one baseline at the bottom. The
 * featured card's cover (the post's image, else a panel with its category and
 * tags) grows to fill the height of the two cards beside it. Styled with theme
 * utilities: the old blog-card / blog-card-featured classes were never
 * defined, so cards rendered as bare text that ran together.
 */
export function BlogCard({ post, featured = false }: BlogCardProps) {
    const href = `/blog/${post.slug}`;
    if (featured) {
        return (
            <Link href={href} className="group flex h-full flex-col overflow-hidden rounded-3xl border border-border bg-card transition-colors hover:border-primary/40">
                {post.coverImage ? (
                    <img src={post.coverImage} alt="" loading="lazy" className="aspect-video w-full flex-1 border-b border-border object-cover" />
                ) : (
                    <div aria-hidden="true" className="relative flex min-h-36 flex-1 flex-col justify-end gap-3 overflow-hidden border-b border-border bg-linear-to-br from-primary/15 via-primary/5 to-violet-500/15 p-6 sm:p-8">
                        <BookOpen className="absolute -right-8 -top-10 h-56 w-56 text-primary/10" strokeWidth={1.25} />
                        <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-primary">{post.category}</span>
                        {post.tags.length ? (
                            <span className="flex flex-wrap gap-1.5">
                                {post.tags.slice(0, 4).map((tag) => (
                                    <span key={tag} className="rounded-full border border-primary/20 bg-background/70 px-2.5 py-1 text-[11px] font-semibold text-foreground/80">
                                        {tag}
                                    </span>
                                ))}
                            </span>
                        ) : null}
                    </div>
                )}
                <div className="flex flex-col p-6 sm:p-8">
                    <div className="flex flex-wrap items-center gap-2">
                        <Badge className="mr-2 bg-primary text-primary-foreground border-0 text-[10px] font-bold uppercase tracking-wider">
                            <BookOpen className="h-3 w-3 mr-1" /> Featured
                        </Badge>
                        <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-wider">
                            {post.category}
                        </Badge>
                    </div>
                    <h3 className="mt-4 text-2xl font-black leading-tight tracking-tight text-foreground transition-colors group-hover:text-primary sm:text-3xl">
                        {post.title}
                    </h3>
                    <p className="mt-3 text-base leading-relaxed text-muted-foreground line-clamp-3">{post.excerpt}</p>
                    <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                        <strong className="font-semibold text-foreground">{post.author}</strong>
                        <span>{formatPostDate(post.date)}</span>
                        {post.readingLabel ? (
                            <span className="inline-flex items-center gap-1.5">
                                <Clock className="h-4 w-4" /> {post.readingLabel} read
                            </span>
                        ) : null}
                    </div>
                    <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-bold text-primary transition-all group-hover:gap-3">
                        Read the post <ArrowRight className="h-4 w-4" />
                    </span>
                </div>
            </Link>
        );
    }

    return (
        <Link href={href} className="group flex h-full flex-col rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary/40">
            {post.coverImage ? (
                <img src={post.coverImage} alt="" loading="lazy" className="mb-4 aspect-video w-full rounded-xl border border-border object-cover" />
            ) : null}
            <div>
                <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-wider">
                    {post.category}
                </Badge>
            </div>
            <h3 className="mt-3 text-lg font-bold leading-snug text-foreground transition-colors group-hover:text-primary">{post.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground line-clamp-3">{post.excerpt}</p>
            <div className="mt-auto flex items-center justify-between gap-3 pt-4 text-xs text-muted-foreground">
                {post.readingLabel ? (
                    <span className="inline-flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" /> {post.readingLabel} read
                    </span>
                ) : <span />}
                <span>{formatPostDate(post.date)}</span>
            </div>
        </Link>
    );
}
