/**
 * The checks behind POST /api/blog-revalidate (app/api/blog-revalidate/route.ts),
 * kept free of Next.js imports so tests/unit/blog-revalidate.test.ts runs them
 * in Node. Only an admin, by the backend's own answer for the caller's token,
 * may refresh the public blog pages.
 */

export type AdminCheck = { ok: true } | { ok: false; status: number; detail: string };

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const MAX_REVALIDATE_SLUGS = 10;

/** The post slugs of a request body ({slugs: [...]}): well-formed ones only, at most MAX_REVALIDATE_SLUGS. */
export function revalidationSlugs(payload: unknown): string[] {
    const raw = payload && typeof payload === 'object' ? (payload as { slugs?: unknown }).slugs : undefined;
    return [...new Set((Array.isArray(raw) ? raw : []).filter((s): s is string => typeof s === 'string' && SLUG.test(s)))]
        .slice(0, MAX_REVALIDATE_SLUGS);
}

type FetchLike = (url: string, init: RequestInit) => Promise<{ ok: boolean; status: number; json: () => Promise<unknown> }>;

/**
 * Is the caller an admin? Asks GET <apiBase>/auth/profile/ with the caller's
 * own Authorization (and X-Session-ID): role 'admin' or is_admin passes, the
 * rule of every /admin page.
 */
export async function confirmBlogAdmin(
    authorization: string,
    sessionId: string | null,
    apiBase: string,
    fetchImpl: FetchLike = fetch as unknown as FetchLike,
): Promise<AdminCheck> {
    if (!/^bearer\s+\S+/i.test(authorization)) return { ok: false, status: 401, detail: 'Sign in as an admin to refresh the blog.' };
    let profile: unknown;
    try {
        const res = await fetchImpl(`${apiBase}/auth/profile/`, {
            headers: {
                Accept: 'application/json',
                Authorization: authorization,
                ...(sessionId ? { 'X-Session-ID': sessionId } : {}),
            },
            cache: 'no-store',
            signal: AbortSignal.timeout(8000),
        });
        if (res.status === 401) return { ok: false, status: 401, detail: 'Your session has expired; sign in again.' };
        if (!res.ok) return { ok: false, status: res.status === 403 ? 403 : 502, detail: 'Could not confirm your admin access.' };
        profile = await res.json();
    } catch {
        return { ok: false, status: 502, detail: 'Could not reach the API to confirm your admin access.' };
    }
    const p = profile && typeof profile === 'object' ? (profile as { role?: unknown; is_admin?: unknown }) : null;
    if (!(p && (p.role === 'admin' || p.is_admin === true))) return { ok: false, status: 403, detail: 'Admin access is needed for this.' };
    return { ok: true };
}
