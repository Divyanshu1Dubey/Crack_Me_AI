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
 *   String checks alone are not enough either. The router resolves the value
 *   with the WHATWG URL parser (`new URL(href, location.href)`), which deletes
 *   tab / LF / CR wherever they appear and reads `\` as `/`. So
 *   `/<TAB>/evil.com` (`?next=/%09/evil.com`) passed every string check and
 *   still became `//evil.com`, i.e. https://evil.com. The value is therefore
 *   also resolved with that parser, accepted only if the origin stays the
 *   same, and returned as the canonical path + query + hash of that parse.
 *
 * Usage:
 *   router.replace(safeInternalPath(searchParams.get('next'), '/dashboard'));
 */

// C0 controls, space, DEL and back-slash. None of them appears in a `next`
// value the app builds (those are always URL-encoded).
const UNSAFE_RAW_CHARS = /[\x00-\x20\x7F\\]/;
// The same for the once-decoded value, except a space: an encoded `%20` is
// normal in a query string.
const UNSAFE_DECODED_CHARS = /[\x00-\x1F\x7F]/;
const ADJACENT_SEPARATORS = /[\/\\][\/\\]/;
// Any http(s) base gives the same answer: a path can only change the origin
// by starting an authority (host) of its own.
const RESOLVE_BASE = 'https://same-origin.invalid';
const RESOLVE_ORIGIN = new URL(RESOLVE_BASE).origin;

export function safeInternalPath(nextParam: string | null | undefined, fallback: string): string {
    if (typeof nextParam !== 'string' || !nextParam) return fallback;
    // Must start with a single forward slash (relative path)
    if (!nextParam.startsWith('/')) return fallback;
    // Reject control characters, whitespace and back-slashes: the URL parser
    // drops tab / LF / CR, so `/\t/evil.com` is really `//evil.com`.
    if (UNSAFE_RAW_CHARS.test(nextParam)) return fallback;
    // Reject protocol-relative URLs (`//evil.com`) and any other doubled
    // separator.
    if (ADJACENT_SEPARATORS.test(nextParam)) return fallback;
    if (nextParam.includes(':')) return fallback;
    // Reject anything that decodes to a fully-qualified URL.
    try {
        const decoded = decodeURIComponent(nextParam);
        if (decoded !== nextParam
            && (ADJACENT_SEPARATORS.test(decoded) || UNSAFE_DECODED_CHARS.test(decoded))) return fallback;
    } catch {
        return fallback;
    }
    // Resolve the value the way the router will and require the same origin.
    let resolved: URL;
    try {
        resolved = new URL(nextParam, RESOLVE_BASE);
    } catch {
        return fallback;
    }
    if (resolved.origin !== RESOLVE_ORIGIN) return fallback;
    const path = `${resolved.pathname}${resolved.search}${resolved.hash}`;
    // A canonical path starting with `//` would be read as a host again.
    if (!path.startsWith('/') || ADJACENT_SEPARATORS.test(path.slice(0, 2))) return fallback;
    return path;
}
