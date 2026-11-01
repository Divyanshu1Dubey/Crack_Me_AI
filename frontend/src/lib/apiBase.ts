/**
 * apiBase.ts -- side-effect-free API base-URL resolution.
 *
 * Shared by the Axios client (api.ts) and lightweight helpers (image URL
 * builders) that must not pull in Axios / Supabase. Originally moved from
 * api.ts; since then a local run (localhost API, local / LAN host, local
 * production build) can no longer be switched to the production API.
 */

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '[::1]']);

/** Loopback, private-network (10/8, 172.16/12, 192.168/16) and *.local hosts. */
const isLocalNetworkHost = (rawHost: string) => {
  const host = rawHost.toLowerCase();
  if (LOOPBACK_HOSTS.has(host) || host.endsWith('.local')) return true;
  const octets = host.split('.').map(Number);
  if (octets.length !== 4 || octets.some((o) => !Number.isInteger(o) || o < 0 || o > 255)) return false;
  const [a, b] = octets;
  return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
};

export const isAppRunningLocally = () => {
  if (typeof window === 'undefined') {
    return process.env.NODE_ENV !== 'production';
  }

  return isLocalNetworkHost(window.location.hostname);
};

export const USE_API_PROXY = isAppRunningLocally() && (process.env.NEXT_PUBLIC_USE_API_PROXY ?? 'false') === 'true';
export const DEFAULT_LOCAL_API_URL = 'http://localhost:8000/api';
export const DEFAULT_PRODUCTION_API_URL = 'https://api.cracklabs.app/api';
export const LEGACY_UNHEALTHY_API_HOSTS = [
  'crackcms-backend.onrender.com',
  '.onrender.com',
  'crackcms-vsthc.ondigitalocean.app',
  '.ondigitalocean.app',
];

export const normalizeApiBaseUrl = (url: string) => {
  const normalized = url.replace(/\/+$/, '');
  return normalized.endsWith('/api') ? normalized : `${normalized}/api`;
};

export const isLocalhostApiUrl = (url: string) => {
  try {
    const parsed = new URL(url);
    return LOOPBACK_HOSTS.has(parsed.hostname.toLowerCase());
  } catch {
    return false;
  }
};

/**
 * A localhost API URL is ignored (production is used instead) only where it
 * cannot be what the operator meant: in a browser on a public host, or while
 * rendering on Vercel. A local `next dev` / `next build` + `next start`, or a
 * page opened from the LAN, keeps the local backend. (On the server
 * isAppRunningLocally() is false for any production build, so SSR of a local
 * production build used to embed production URLs.)
 */
export const shouldIgnoreConfiguredApiUrl = (url: string) => {
  if (!isLocalhostApiUrl(url)) return false;
  if (typeof window === 'undefined') return Boolean(process.env.VERCEL);
  return !isAppRunningLocally();
};

export const isKnownUnhealthyApiHost = (url: string) =>
  LEGACY_UNHEALTHY_API_HOSTS.some((host) => url.includes(host));

export const resolveApiBaseUrl = () => {
  if (USE_API_PROXY) {
    return '/api/proxy';
  }

  const configured = (process.env.NEXT_PUBLIC_API_URL || '').trim();
  if (configured) {
    const normalized = normalizeApiBaseUrl(configured);
    if (shouldIgnoreConfiguredApiUrl(normalized) || isKnownUnhealthyApiHost(normalized)) {
      return DEFAULT_PRODUCTION_API_URL;
    }
    return normalized;
  }

  return process.env.NODE_ENV === 'production' ? DEFAULT_PRODUCTION_API_URL : DEFAULT_LOCAL_API_URL;
};

export const API_BASE_URL = resolveApiBaseUrl();

/**
 * Failover target for 502/503/504 responses (api.ts). Returns the primary
 * base itself when failover must not happen.
 *
 * Without NEXT_PUBLIC_API_FALLBACK_URL the target used to be the production
 * API for everyone, so a local run whose backend answered 502/503/504 (or a
 * proxy in front of it) silently replayed the request against production.
 * A local run now never fails over to a remote API (CFG-10).
 */
export const resolveFallbackApiBaseUrl = (
  primary: string = API_BASE_URL,
  configured: string = (process.env.NEXT_PUBLIC_API_FALLBACK_URL || '').trim(),
) => {
  if (USE_API_PROXY) return primary;
  const primaryIsLocal = isLocalhostApiUrl(primary);
  if (!configured) {
    return primaryIsLocal || isAppRunningLocally() ? primary : DEFAULT_PRODUCTION_API_URL;
  }
  const fallback = normalizeApiBaseUrl(configured);
  if (primaryIsLocal && !isLocalhostApiUrl(fallback)) return primary;
  return shouldIgnoreConfiguredApiUrl(fallback) ? DEFAULT_PRODUCTION_API_URL : fallback;
};

/** Absolute (or proxy-relative) URL for an API path such as `/questions/images/1/serve/`. */
export const apiUrl = (path: string) => `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
