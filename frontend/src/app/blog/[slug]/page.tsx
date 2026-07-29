import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { BlogPostLayout } from '@/components/BlogPostLayout';
import { buildPageMetadata } from '@/lib/metadata';
import { getAllPostSlugs, getPostBySlug } from '@/lib/blog';

interface PageProps {
    params: Promise<{ slug: string }>;
}

/**
 * Pre-render every known blog post at build time. New posts get picked up
 * automatically as long as they are registered in `src/lib/blog.ts`.
 */
export async function generateStaticParams() {
    return getAllPostSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { slug } = await params;
    const post = getPostBySlug(slug);
    if (!post) {
        return buildPageMetadata({
            title: 'Post not found — CrackCMS Blog',
            description: 'The blog post you were looking for could not be found.',
            path: `/blog/${slug}`,
            noindex: true,
        });
    }
    return buildPageMetadata({
        title: `${post.title} — CrackCMS Blog`,
        description: post.description,
        path: `/blog/${post.slug}`,
        image: post.coverImage ?? '/cms-circle-logo.png',
        type: 'article',
        keywords: [
            post.category,
            ...post.tags,
            'UPSC CMS',
            'NEET PG',
            'medical exam preparation',
            'CrackCMS blog',
        ],
    });
}

export default async function BlogPostPage({ params }: PageProps) {
    const { slug } = await params;
    const post = getPostBySlug(slug);
    if (!post) notFound();
    return <BlogPostLayout post={post} />;
}
