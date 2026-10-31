/**
 * apiBase.ts -- side-effect-free API base-URL resolution.
 *
 * Shared by the Axios client (api.ts) and lightweight helpers (image URL
 * builders) that must not pull in Axios / Supabase. Moved verbatim from
 * api.ts; behaviour is unchanged.
 */

export const isAppRunningLocally = () => {
  if (typeof window === 'undefined') {
    return process.env.NODE_ENV !== 'production';
  }

  const host = window.location.hostname.toLowerCase();
  return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
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
    const host = parsed.hostname.toLowerCase();
    return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
  } catch {
    return false;
  }
};

export const shouldIgnoreConfiguredApiUrl = (url: string) =>
  isLocalhostApiUrl(url) && !isAppRunningLocally();

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

/** Absolute (or proxy-relative) URL for an API path such as `/questions/images/1/serve/`. */
export const apiUrl = (path: string) => `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
