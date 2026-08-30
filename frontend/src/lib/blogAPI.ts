/**
 * blogAPI — Blog management endpoints for the admin control tower.
 *
 * Base path: /api/blog/
 * Auth: Supabase JWT + IsAdminUser (all endpoints require admin role).
 *
 * CRUD actions:
 *   list         GET  /api/blog/posts/           (filterable, searchable, paginated)
 *   get          GET  /api/blog/posts/:id/
 *   getBySlug    GET  /api/blog/posts/by-slug/:slug/
 *   create       POST /api/blog/posts/
 *   update       PATCH /api/blog/posts/:id/
 *   remove       DELETE /api/blog/posts/:id/
 *   togglePublish POST /api/blog/posts/:id/toggle-publish/
 */
import api from './api';

export interface BlogPostAdmin {
    id: number;
    slug: string;
    title: string;
    description: string;
    excerpt: string;
    cover_image: string;
    category: string;
    subcategory: string;
    tags: string[];
    difficulty: 'beginner' | 'intermediate' | 'advanced';
    author_id: string;
    reviewed_by: string;
    author: string;
    author_role: string;
    date_published: string;
    date_modified: string;
    updated_at: string;
    reading_time: string;
    word_count: number | null;
    primary_cta: Record<string, unknown>;
    related_exam_paths: string[];
    faqs: { q: string; a: string }[];
    toc: { id: string; label: string }[];
    references: { label: string; url?: string; published?: string }[];
    revision_log: { date: string; note: string }[];
    body: string;
    prelude: string;
    outro: string;
    pinned: boolean;
    trending: boolean;
    is_published: boolean;
    created_at: string;
    updated: string;
}

export interface BlogListParams {
    page?: number;
    search?: string;
    category?: string;
    difficulty?: string;
    is_published?: string;
    pinned?: string;
    ordering?: string;
}

export const blogAPI = {
    list: (params?: BlogListParams) =>
        api.get('/blog/posts/', { params }),

    get: (id: number) =>
        api.get(`/blog/posts/${id}/`),

    getBySlug: (slug: string) =>
        api.get(`/blog/posts/by-slug/${encodeURIComponent(slug)}/`),

    create: (data: Partial<BlogPostAdmin>) =>
        api.post('/blog/posts/', data),

    update: (id: number, data: Partial<BlogPostAdmin>) =>
        api.patch(`/blog/posts/${id}/`, data),

    remove: (id: number) =>
        api.delete(`/blog/posts/${id}/`),

    togglePublish: (id: number) =>
        api.post(`/blog/posts/${id}/toggle-publish/`),
};
