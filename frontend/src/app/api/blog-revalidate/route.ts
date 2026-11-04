import { revalidatePath, revalidateTag } from 'next/cache';
import { NextResponse, type NextRequest } from 'next/server';
import { blogApiBaseUrl } from '@/lib/blog';
import { confirmBlogAdmin, revalidationSlugs } from '@/lib/blogRevalidate';

/**
 * POST /api/blog-revalidate  { slugs: ["post-slug", ...] }  (Authorization: Bearer <the admin's token>)
 *
 * /admin/blog calls this after saving, (un)publishing or deleting a post so
 * the public pages show the change on the next visit instead of within
 * ~2 × BLOG_REVALIDATE_SECONDS. The caller must be an admin by the backend's
 * own answer (lib/blogRevalidate confirmBlogAdmin: its token is sent to
 * GET /api/auth/profile/; role 'admin' / is_admin passes). Then the
 * 'blog'-tagged API reads (catalog, posts: every /blog page, the feed and the
 * sitemap) expire, and /blog plus the named posts are re-rendered on their
 * next request.
 */
export const dynamic = 'force-dynamic';

function answer(status: number, body: Record<string, unknown>) {
    return NextResponse.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
}

export async function POST(request: NextRequest) {
    const check = await confirmBlogAdmin(
        request.headers.get('authorization') ?? '',
        request.headers.get('x-session-id'),
        blogApiBaseUrl(),
    );
    if (!check.ok) return answer(check.status, { detail: check.detail });

    let payload: unknown = null;
    try {
        payload = await request.json();
    } catch {
        payload = null;
    }
    const slugs = revalidationSlugs(payload);

    // Expire (not just mark stale): the next visitor gets the saved post.
    revalidateTag('blog', { expire: 0 });
    revalidatePath('/blog');
    for (const slug of slugs) revalidatePath(`/blog/${slug}`);
    return answer(200, { revalidated: true, slugs });
}
