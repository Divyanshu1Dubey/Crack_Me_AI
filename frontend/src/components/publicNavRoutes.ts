/**
 * Routes that get the global public nav (components/PublicNav.tsx). Kept as
 * a plain module so it can be unit-tested with Node.
 *
 * Only public marketing pages with no header of their own belong here. Not
 * listed on purpose: "/" (the homepage renders the bar itself, under its
 * countdown banner), app pages (they render <Sidebar/><Header/> or AppShell),
 * /resources and /contact (they use the app shell), and the auth pages
 * (AuthShell).
 */
export const PUBLIC_NAV_PREFIXES = [
    '/about',
    '/cms',
    '/exams',
    '/neet-pg',
    '/ini-cet',
    '/fmge',
    '/usmle',
    '/medical-officer',
    '/government-doctor-jobs',
    '/guides',
    '/tools',
    '/blog',
    '/privacy-policy',
    '/terms',
    '/cookie-policy',
    '/refund-policy',
    '/disclaimer',
    '/editorial-policy',
    '/medical-review-policy',
    '/ai-attribution-policy',
] as const;

/** True for a listed prefix itself or any path below it ("/cms/salary"). */
export function isPublicNavPath(pathname: string | null | undefined): boolean {
    if (!pathname) return false;
    return PUBLIC_NAV_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
