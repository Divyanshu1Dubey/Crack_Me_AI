/**
 * The blog article renderer without Next.js imports (plain .ts so node unit
 * tests render it with react-dom/server): markdown -> the .blog-prose article,
 * through the pipeline of lib/blogMarkdown. BlogArticle.tsx wraps it with
 * next/link for internal links; the editor's Preview tab uses the same one.
 * No hooks: it renders on the server and in the browser alike.
 */
import { createElement, type ComponentType, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import { BLOG_RENDER_REMARK_PLUGINS, blogRehypePlugins, type BlogArticleOptions } from '@/lib/blogMarkdown';

export interface LinkLikeProps {
    href: string;
    className?: string;
    children?: ReactNode;
}

export interface BlogArticleBodyProps extends BlogArticleOptions {
    markdown: string;
    id?: string;
    className?: string;
    /** Renders internal links (/questions, /blog/...): next/link on the site, a plain <a> when unset. */
    linkComponent?: ComponentType<LinkLikeProps>;
}

const INTERNAL = /^\/(?!\/)/;

export function BlogArticleBody({ markdown, id, className, linkComponent, ...options }: BlogArticleBodyProps) {
    const components: Components = {};
    if (linkComponent) {
        components.a = ({ node: _node, href, children, ...rest }) =>
            typeof href === 'string' && INTERNAL.test(href)
                ? createElement(linkComponent, { href, ...rest }, children)
                : createElement('a', { href, ...rest }, children);
    }
    return createElement(
        'div',
        { id, className: ['blog-article', 'blog-prose', className].filter(Boolean).join(' ') },
        createElement(
            ReactMarkdown,
            { remarkPlugins: BLOG_RENDER_REMARK_PLUGINS, rehypePlugins: blogRehypePlugins(options), components },
            markdown,
        ),
    );
}
