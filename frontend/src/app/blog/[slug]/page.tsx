import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { BlogPostLayout } from '@/components/BlogPostLayout';
import { buildPageMetadata } from '@/lib/metadata';
import { linkRelatedPosts, loadBlogCatalog, loadBlogPost, postSocialImagePath } from '@/lib/blog';

interface PageProps {
    params: Promise<{ slug: string }>;
}

// Published posts from the database (edited at /admin/blog), regenerated at
// most every 5 minutes (BLOG_REVALIDATE_SECONDS). A post published after the
// build renders on its first request; a draft or deleted post is a 404.
export const revalidate = 300;
export const dynamicParams = true;

/** Pre-render every published post at build time (the static posts if the API is unreachable). */
export async function generateStaticParams() {
    return (await loadBlogCatalog()).map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { slug } = await params;
    const post = await loadBlogPost(slug);
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
        image: postSocialImagePath(post),
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
    const [post, catalog] = await Promise.all([loadBlogPost(slug), loadBlogCatalog()]);
    if (!post) notFound();
    // BlogPostLayout picks "Related reading" from the published posts.
    linkRelatedPosts(post, catalog);
    return <BlogPostLayout post={post} />;
}
