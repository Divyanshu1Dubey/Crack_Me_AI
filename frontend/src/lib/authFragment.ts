/**
 * authFragment.ts -- the one-time values of an emailed sign-in link.
 *
 * The Django-native backend (AUTH_PROVIDER=django) mails links whose secret
 * part is in the URL FRAGMENT, never in the query string:
 *   /verify-email#token=<t>              finish a new sign-up
 *   /verify-email#uid=<u>&token=<t>      confirm an existing account's email
 *   /reset-password#uid=<u>&token=<t>    set a new password
 *   /connect-google#token=<t>            link a Google account
 * Browsers never send the fragment to a server (no access logs, no Referer),
 * and the pages remove it from the address bar as soon as they have read it,
 * so it does not stay in the history, a bookmark or a copied URL.
 *
 * No imports: unit-tested directly (tests/unit/auth-fragment.test.ts).
 */

export interface AuthLinkParams {
  token: string | null;
  uid: string | null;
}

const MAX_FRAGMENT_LENGTH = 4096;
const MAX_VALUE_LENGTH = 2048;
// Every value the backend puts in these links is URL-safe: base64url uids
// and tokens (secrets.token_urlsafe), base36-hex password-reset tokens, and
// django.core.signing tokens (base64url with '.' and ':'). Anything else
// (whitespace, quotes, '%' left by a mangled encoding, ...) is not a link
// value.
const LINK_VALUE = /^[A-Za-z0-9._:~=-]+$/;

const cleanValue = (value: string | null): string | null => {
  const trimmed = (value ?? '').trim();
  if (!trimmed || trimmed.length > MAX_VALUE_LENGTH || !LINK_VALUE.test(trimmed)) return null;
  return trimmed;
};

/** `token` / `uid` of a fragment such as `#uid=MTI&token=abc-123` (`null` when absent or malformed). */
export function parseAuthFragment(hash: string | null | undefined): AuthLinkParams {
  const raw = typeof hash === 'string' ? (hash.startsWith('#') ? hash.slice(1) : hash) : '';
  if (!raw || raw.length > MAX_FRAGMENT_LENGTH) return { token: null, uid: null };
  let params: URLSearchParams;
  try {
    params = new URLSearchParams(raw);
  } catch {
    return { token: null, uid: null };
  }
  return { token: cleanValue(params.get('token')), uid: cleanValue(params.get('uid')) };
}

type LocationAndHistory = {
  location: Pick<Location, 'hash' | 'pathname' | 'search'>;
  history: Pick<History, 'replaceState'>;
};

const browserWindow = (): LocationAndHistory | undefined =>
  typeof window === 'undefined' ? undefined : window;

/**
 * Remove the fragment from the address bar, keeping the path and the query
 * string. Uses history.replaceState, which Next.js' App Router integrates
 * with (no navigation, no re-render of the page).
 */
export function stripAuthFragment(win: LocationAndHistory | undefined = browserWindow()): void {
  if (!win || !win.location.hash) return;
  try {
    win.history.replaceState(null, '', `${win.location.pathname}${win.location.search}`);
  } catch {
    // Some embedded browsers refuse history changes: the values were still read.
  }
}

/** Read the link's values once and clear them from the address bar. */
export function takeAuthFragment(win: LocationAndHistory | undefined = browserWindow()): AuthLinkParams {
  if (!win) return { token: null, uid: null };
  const params = parseAuthFragment(win.location.hash);
  stripAuthFragment(win);
  return params;
}
