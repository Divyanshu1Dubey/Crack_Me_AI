import Link from 'next/link';
import { ArrowRight, BookOpen, Clock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { BlogPost } from '@/lib/blog';
import { formatPostDate } from '@/lib/blog';

interface BlogCardProps {
    post: BlogPost;
    featured?: boolean;
}

/**
 * Card for the /blog index grid. Optionally highlights the featured
 * post (larger card). Styled with theme utilities: the old blog-card /
 * blog-card-featured classes were never defined, so cards rendered as bare
 * text that ran together.
 */
export function BlogCard({ post, featured = false }: BlogCardProps) {
    const href = `/blog/${post.slug}`;
    if (featured) {
        return (
            <Link href={href} className="group block rounded-3xl border border-border bg-card p-6 sm:p-8 transition-colors hover:border-primary/40">
                <Badge className="mr-2 bg-primary text-primary-foreground border-0 text-[10px] font-bold uppercase tracking-wider">
                    <BookOpen className="h-3 w-3 mr-1" /> Featured
                </Badge>
                <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-wider">
                    {post.category}
                </Badge>
                <h2 className="mt-3 text-2xl font-black tracking-tight text-foreground sm:text-3xl">
                    {post.title}
                </h2>
                <p className="mt-3 text-sm text-muted-foreground line-clamp-3">{post.excerpt}</p>
                <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                        <strong className="text-foreground">{post.author}</strong>
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                        {formatPostDate(post.dateModified)}
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" /> {post.readingTime}
                    </span>
                </div>
                <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-bold text-primary group-hover:gap-3 transition-all">
                    Read the post <ArrowRight className="h-4 w-4" />
                </span>
            </Link>
        );
    }

    return (
        <Link href={href} className="group block rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary/40">
            <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-wider">
                {post.category}
            </Badge>
            <h3 className="mt-3 text-lg font-black text-foreground">{post.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground line-clamp-3">{post.excerpt}</p>
            <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" /> {post.readingTime}
                </span>
                <span>{formatPostDate(post.dateModified)}</span>
            </div>
            <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-bold text-primary group-hover:gap-2 transition-all">
                Read the post <ArrowRight className="h-3.5 w-3.5" />
            </span>
        </Link>
    );
}
