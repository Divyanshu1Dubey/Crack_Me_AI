/**
 * Upstream selection for the API proxy (app/api/proxy/[...path]/route.ts).
 *
 * Lives outside route.ts because a Next.js route file may only export HTTP
 * method handlers (and route config); this keeps the rule unit-testable
 * (tests/unit/proxy-upstream.test.ts).
 */

export const DEFAULT_BACKEND_API_URL = 'https://api.cracklabs.app/api';
export const DEFAULT_LOCAL_BACKEND_API_URL = 'http://127.0.0.1:8000/api';

const LEGACY_UNHEALTHY_API_HOSTS = [
  'crackcms-backend.onrender.com',
  '.onrender.com',
  'crackcms-vsthc.ondigitalocean.app',
  '.ondigitalocean.app',
];
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '[::1]']);

/**
 * Loopback, private-network (10/8, 172.16/12, 192.168/16) and *.local
 * hosts. The same rule as isLocalNetworkHost in lib/apiBase.ts, which turns
 * USE_API_PROXY on for exactly these hosts -- so the proxy must treat them as
 * local too, or a production build opened from the LAN (phone testing) with
 * NEXT_PUBLIC_USE_API_PROXY=true was proxied to the production API (CFG-10).
 */
export const isLocalNetworkHost = (rawHost: string) => {
  const host = rawHost.toLowerCase();
  if (LOOPBACK_HOSTS.has(host) || host.endsWith('.local')) return true;
  const octets = host.split('.').map(Number);
  if (octets.length !== 4 || octets.some((o) => !Number.isInteger(o) || o < 0 || o > 255)) return false;
  const [a, b] = octets;
  return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
};

const normalizeApiBaseUrl = (url: string) => {
  const normalized = url.replace(/\/+$/, '');
  return normalized.endsWith('/api') ? normalized : `${normalized}/api`;
};

const isKnownUnhealthyApiHost = (url: string) =>
  LEGACY_UNHEALTHY_API_HOSTS.some((host) => url.includes(host));

const configuredApiBaseUrl = (value: string | undefined) => {
  const configured = (value || '').trim();
  if (!configured) return '';
  const normalized = normalizeApiBaseUrl(configured);
  return isKnownUnhealthyApiHost(normalized) ? '' : normalized;
};

export type ProxyUpstreamEnv = {
  NODE_ENV?: string;
  BACKEND_API_URL?: string;
  BACKEND_API_FALLBACK_URL?: string;
};

/**
 * The browser only uses this proxy when the app runs on a local / LAN host
 * (lib/apiBase.ts USE_API_PROXY). Requests served on such a host -- or by a
 * dev server -- go to BACKEND_API_URL or the local backend and never fall
 * back to production unless BACKEND_API_FALLBACK_URL says so; a local session
 * must not read from or write to the production API by accident. The
 * deployed site keeps its previous behaviour (production API, no fallback).
 */
export const resolveBackendApiBaseUrls = (hostname: string, env: ProxyUpstreamEnv) => {
  const servedLocally = env.NODE_ENV !== 'production' || isLocalNetworkHost(hostname);
  if (!servedLocally) {
    return { primary: DEFAULT_BACKEND_API_URL, fallback: '' };
  }
  const primary = configuredApiBaseUrl(env.BACKEND_API_URL) || DEFAULT_LOCAL_BACKEND_API_URL;
  const fallback = configuredApiBaseUrl(env.BACKEND_API_FALLBACK_URL);
  return { primary, fallback: fallback && fallback !== primary ? fallback : '' };
};
