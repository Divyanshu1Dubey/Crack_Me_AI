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
 * up, with the date and reading time on one baseline at the bottom. Styled with
 * theme utilities: the old blog-card / blog-card-featured classes were never
 * defined, so cards rendered as bare text that ran together.
 */
export function BlogCard({ post, featured = false }: BlogCardProps) {
    const href = `/blog/${post.slug}`;
    if (featured) {
        return (
            <Link href={href} className="group flex h-full flex-col rounded-3xl border border-border bg-card p-6 sm:p-8 transition-colors hover:border-primary/40">
                {post.coverImage ? (
                    <img src={post.coverImage} alt="" loading="lazy" className="mb-6 aspect-video w-full rounded-2xl border border-border object-cover" />
                ) : null}
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
                <p className="mt-4 text-base leading-relaxed text-muted-foreground line-clamp-4">{post.excerpt}</p>
                <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-2 pt-6 text-sm text-muted-foreground">
                    <strong className="font-semibold text-foreground">{post.author}</strong>
                    <span>{formatPostDate(post.date)}</span>
                    <span className="inline-flex items-center gap-1.5">
                        <Clock className="h-4 w-4" /> {post.readingLabel} read
                    </span>
                </div>
                <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-bold text-primary transition-all group-hover:gap-3">
                    Read the post <ArrowRight className="h-4 w-4" />
                </span>
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
                <span className="inline-flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" /> {post.readingLabel} read
                </span>
                <span>{formatPostDate(post.date)}</span>
            </div>
        </Link>
    );
}
