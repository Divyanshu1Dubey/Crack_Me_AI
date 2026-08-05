/**
 * Safe redirect-path guard.
 *
 * Returns the supplied path only if it is a same-origin relative path. Any
 * value that could redirect the user off-site (protocol-relative URLs,
 * absolute URLs, or paths containing a scheme separator) is rejected.
 *
 * Why this exists:
 *   Auth flows accept a `?next=` query parameter and pass it straight to
 *   `router.push`. Without an origin check, an attacker can craft a link like
 *   `/auth/callback?next=//evil.com/phish` that bounces a freshly-signed-in
 *   user to a malicious domain — a textbook open-redirect.
 *
 *   The previous check (`path.startsWith('/')`) is insufficient because
 *   `//evil.com` also starts with a slash (it's a protocol-relative URL).
 *
 * Usage:
 *   router.replace(safeInternalPath(searchParams.get('next'), '/dashboard'));
 */
export function safeInternalPath(nextParam: string | null | undefined, fallback: string): string {
    if (!nextParam) return fallback;
    // Must start with a single forward slash (relative path)
    if (!nextParam.startsWith('/')) return fallback;
    // Reject protocol-relative URLs (`//evil.com`)
    if (nextParam.startsWith('//')) return fallback;
    // Reject anything containing a scheme separator (`/path`, `/\\evil.com`,
    // or back-slash variants are caught by the regex below).
    if (/[\/\\][\/\\]/.test(nextParam)) return fallback;
    if (nextParam.includes(':')) return fallback;
    // Reject anything that decodes to a fully-qualified URL.
    try {
        const decoded = decodeURIComponent(nextParam);
        if (decoded !== nextParam && /[\/\\][\/\\]/.test(decoded)) return fallback;
    } catch {
        return fallback;
    }
    return nextParam;
}
