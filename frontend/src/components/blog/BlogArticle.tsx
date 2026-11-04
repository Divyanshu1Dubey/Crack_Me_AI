import Link from 'next/link';
import { BlogArticleBody, type BlogArticleBodyProps } from './blogArticleCore';

/**
 * A blog post body as the published article (.blog-prose): headings with
 * anchor ids, callouts, figures, scrollable tables, sanitized raw HTML. A
 * Server Component on the post page; the /admin/blog preview renders the same
 * component in the browser. See lib/blogMarkdown for the markdown it reads.
 */
export function BlogArticle(props: Omit<BlogArticleBodyProps, 'linkComponent'>) {
    return <BlogArticleBody {...props} linkComponent={Link} />;
}
