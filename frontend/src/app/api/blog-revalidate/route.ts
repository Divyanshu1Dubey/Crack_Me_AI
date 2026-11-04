import { revalidatePath, revalidateTag } from 'next/cache';
import { NextResponse, type NextRequest } from 'next/server';
import { blogApiBaseUrl } from '@/lib/blog';

/**
 * POST /api/blog-revalidate  { slugs: ["post-slug", ...] }  (Authorization: Bearer <the admin's token>)
 *
 * /admin/blog calls this after saving, (un)publishing or deleting a post so
 * the public pages show the change on the next visit instead of within
 * ~2 × BLOG_REVALIDATE_SECONDS. The caller must be an admin by the backend's
 * own answer: its token is sent to GET /api/auth/profile/ and only role
 * 'admin' / is_admin passes (the rule of every /admin page). Then the
 * 'blog'-tagged API reads (catalog, posts: every /blog page, the feed and the
 * sitemap) expire, and /blog plus the named posts are re-rendered on their
 * next request.
 */
export const dynamic = 'force-dynamic';

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const MAX_SLUGS = 10;

function answer(status: number, body: Record<string, unknown>) {
    return NextResponse.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
}

export async function POST(request: NextRequest) {
    const authorization = request.headers.get('authorization') ?? '';
    if (!/^bearer\s+\S+/i.test(authorization)) return answer(401, { detail: 'Sign in as an admin to refresh the blog.' });

    let payload: unknown = null;
    try {
        payload = await request.json();
    } catch {
        payload = null;
    }
    const raw = payload && typeof payload === 'object' ? (payload as { slugs?: unknown }).slugs : undefined;
    const slugs = (Array.isArray(raw) ? raw : [])
        .filter((s): s is string => typeof s === 'string' && SLUG.test(s))
        .slice(0, MAX_SLUGS);

    let profile: { role?: unknown; is_admin?: unknown } | null = null;
    try {
        const sessionId = request.headers.get('x-session-id');
        const res = await fetch(`${blogApiBaseUrl()}/auth/profile/`, {
            headers: {
                Accept: 'application/json',
                Authorization: authorization,
                ...(sessionId ? { 'X-Session-ID': sessionId } : {}),
            },
            cache: 'no-store',
            signal: AbortSignal.timeout(8000),
        });
        if (res.status === 401) return answer(401, { detail: 'Your session has expired; sign in again.' });
        if (!res.ok) return answer(res.status === 403 ? 403 : 502, { detail: 'Could not confirm your admin access.' });
        profile = await res.json();
    } catch {
        return answer(502, { detail: 'Could not reach the API to confirm your admin access.' });
    }
    if (!(profile && (profile.role === 'admin' || profile.is_admin === true))) {
        return answer(403, { detail: 'Admin access is needed for this.' });
    }

    // Expire (not just mark stale): the next visitor gets the saved post.
    revalidateTag('blog', { expire: 0 });
    revalidatePath('/blog');
    for (const slug of slugs) revalidatePath(`/blog/${slug}`);
    return answer(200, { revalidated: true, slugs });
}
