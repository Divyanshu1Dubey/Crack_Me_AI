/**
 * Leave the page after the session changed (sign-in, sign-out) with a full page load instead of
 * router.push / router.replace.
 *
 * The App Router caches prefetched routes on the client. While a visitor is signed out, the
 * middleware answers a prefetch of a protected route (/questions, /tests, ...) with a redirect to
 * /login, and that redirect stays in the router cache: after a client-side navigation into the
 * signed-in app, every click on such a link replayed it and sent the user back to /login although
 * the session was valid (2026-11-03, django mode). A document load starts with an empty router
 * cache and carries the new presence cookie. The middleware also no longer redirects prefetches
 * (utils/supabase/middleware.ts); this covers routers that cached one before.
 *
 * `path` must already be a safe internal path (safeInternalPath or a literal).
 */
export const navigateAfterAuthChange = (path: string, options: { replace?: boolean } = {}): void => {
    if (typeof window === 'undefined') return;
    if (options.replace) {
        window.location.replace(path);
    } else {
        window.location.assign(path);
    }
};
