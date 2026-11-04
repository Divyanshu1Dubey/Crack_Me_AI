/**
 * blogAPI — blog management endpoints for /admin/blog.
 *
 * Base path: /api/blog/ (backend/blog_engine). The database is the source of
 * truth of the public blog: the /blog pages render the published posts
 * server-side (lib/blog.ts loadBlogCatalog / loadBlogPost, ISR), so a post
 * saved here shows on the site within about 2 × BLOG_REVALIDATE_SECONDS.
 *
 * Auth: reads of published posts are public; drafts and every write need an
 * admin (role 'admin', superuser, or a staff account).
 *
 *   list          GET    /api/blog/posts/            (?search, ?category, ?is_published, ?ordering, ?page, ?page_size)
 *   facets        GET    /api/blog/posts/facets/     (admin: totals + categories)
 *   get           GET    /api/blog/posts/:id/
 *   getBySlug     GET    /api/blog/posts/by-slug/:slug/
 *   create        POST   /api/blog/posts/
 *   update        PATCH  /api/blog/posts/:id/
 *   remove        DELETE /api/blog/posts/:id/
 *   togglePublish POST   /api/blog/posts/:id/toggle-publish/
 *   uploadImage   POST   /api/blog/images/           (multipart `file`; answers {src, width, height, ...})
 *   revalidate    POST   <this site>/api/blog-revalidate  (Next.js: refresh the public pages now)
 *
 * word_count / reading_time in every response are computed by the API from
 * the body (blog_engine.text_stats); is_thin: under THIN_POST_WORDS words.
 *
 * The public catalog (GET /api/blog/posts/catalog/) is read by the Next.js
 * server, not through this client.
 */
import api from './api';
import { API_BASE_URL } from './apiBase';
import type { BlogPostRecord } from './blog';

/** A post as the admin API returns it. */
export interface BlogPostAdmin extends BlogPostRecord {
    id: number;
    is_published: boolean;
    created_at: string;
    updated: string;
}

/** A row of the admin list (BlogPostListSerializer: no body or structured lists). */
export type BlogPostAdminRow = Pick<
    BlogPostAdmin,
    | 'id'
    | 'slug'
    | 'title'
    | 'description'
    | 'excerpt'
    | 'cover_image'
    | 'category'
    | 'subcategory'
    | 'tags'
    | 'difficulty'
    | 'author_id'
    | 'reviewed_by'
    | 'author'
    | 'author_role'
    | 'date_published'
    | 'date_modified'
    | 'updated_at'
    | 'reading_time'
    | 'word_count'
    | 'pinned'
    | 'trending'
    | 'is_published'
    | 'created_at'
    | 'updated'
> & {
    /** The body is empty or the old seed placeholder: never shown publicly. */
    is_stub: boolean;
    /** Under THIN_POST_WORDS words: a post to expand. */
    is_thin?: boolean;
};

export interface BlogFacets {
    total: number;
    published: number;
    drafts: number;
    /** Posts under `thin_words` words (absent from an older API). */
    thin?: number;
    thin_words?: number;
    categories: { name: string; count: number }[];
}

export interface BlogListParams {
    page?: number;
    page_size?: number;
    search?: string;
    category?: string;
    difficulty?: string;
    is_published?: string;
    pinned?: string;
    thin?: string;
    ordering?: string;
}

/** POST /api/blog/images/ answer: `src` is the path to put in the post (on the API origin). */
export interface BlogImageUpload {
    src: string;
    width: number;
    height: number;
    bytes: number;
    mime: string;
}

/** The API's origin ('' when the API is reached through a relative proxy path). */
export function blogApiOrigin(base: string = API_BASE_URL): string {
    try {
        return /^https?:\/\//i.test(base) ? new URL(base).origin : '';
    } catch {
        return '';
    }
}

/** A stored /api/... media path as the browser loads it. */
export function blogMediaUrl(src: string, origin: string = blogApiOrigin()): string {
    return src.startsWith('/api/') && origin ? `${origin}${src}` : src;
}

export const blogAPI = {
    list: (params?: BlogListParams) =>
        api.get('/blog/posts/', { params }),

    facets: () =>
        api.get<BlogFacets>('/blog/posts/facets/'),

    get: (id: number) =>
        api.get<BlogPostAdmin>(`/blog/posts/${id}/`),

    getBySlug: (slug: string) =>
        api.get<BlogPostAdmin>(`/blog/posts/by-slug/${encodeURIComponent(slug)}/`),

    create: (data: Partial<BlogPostAdmin>) =>
        api.post<BlogPostAdmin>('/blog/posts/', data),

    update: (id: number, data: Partial<BlogPostAdmin>) =>
        api.patch<BlogPostAdmin>(`/blog/posts/${id}/`, data),

    remove: (id: number) =>
        api.delete(`/blog/posts/${id}/`),

    togglePublish: (id: number) =>
        api.post<{ id: number; is_published: boolean; message: string }>(`/blog/posts/${id}/toggle-publish/`),

    uploadImage: (file: File) => {
        const form = new FormData();
        form.append('file', file);
        // Content-Type undefined: the browser sets multipart/form-data with its boundary.
        return api.post<BlogImageUpload>('/blog/images/', form, { headers: { 'Content-Type': undefined } });
    },

    /**
     * Refresh the public blog pages now (this site's route handler checks the
     * caller is an admin with the API). Without it they update within ~10 min.
     */
    revalidate: (slugs: string[]) =>
        api.post<{ revalidated: boolean; slugs: string[] }>(
            `${typeof window === 'undefined' ? '' : window.location.origin}/api/blog-revalidate`,
            { slugs: slugs.filter(Boolean) },
        ),
};
