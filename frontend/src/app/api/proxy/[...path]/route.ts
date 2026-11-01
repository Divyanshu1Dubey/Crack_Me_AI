import { NextRequest } from 'next/server';

const DEFAULT_BACKEND_API_URL = 'https://api.cracklabs.app/api';
const DEFAULT_LOCAL_BACKEND_API_URL = 'http://127.0.0.1:8000/api';
const DEFAULT_TIMEOUT_MS = Number(process.env.PROXY_UPSTREAM_TIMEOUT_MS || 15000);
const LEGACY_UNHEALTHY_API_HOSTS = [
  'crackcms-backend.onrender.com',
  '.onrender.com',
  'crackcms-vsthc.ondigitalocean.app',
  '.ondigitalocean.app',
];
const LOCAL_HOSTNAMES = new Set(['localhost', '127.0.0.1', '::1', '[::1]']);
// Only these are replayed against the fallback after a failure: a POST or
// PATCH that hit a 5xx may already have been applied.
const RETRYABLE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

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

/**
 * The browser only uses this proxy when the app runs on localhost
 * (lib/apiBase.ts USE_API_PROXY). Requests served on a local hostname -- or
 * by a dev server -- go to BACKEND_API_URL or the local backend and never
 * fall back to production unless BACKEND_API_FALLBACK_URL says so; a local
 * session must not read from or write to the production API by accident.
 * The deployed site keeps its previous behaviour (production API, no
 * fallback).
 */
const resolveBackendApiBaseUrls = (request: NextRequest) => {
  const servedLocally =
    process.env.NODE_ENV !== 'production'
    || LOCAL_HOSTNAMES.has(request.nextUrl.hostname.toLowerCase());
  if (!servedLocally) {
    return { primary: DEFAULT_BACKEND_API_URL, fallback: '' };
  }
  const primary = configuredApiBaseUrl(process.env.BACKEND_API_URL) || DEFAULT_LOCAL_BACKEND_API_URL;
  const fallback = configuredApiBaseUrl(process.env.BACKEND_API_FALLBACK_URL);
  return { primary, fallback: fallback && fallback !== primary ? fallback : '' };
};

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
]);

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

const sanitizePathParts = (pathParts: string[]) => {
  return pathParts.map((segment) => {
    const decoded = (() => {
      try {
        return decodeURIComponent(segment);
      } catch {
        return segment;
      }
    })();

    if (
      decoded === ''
      || decoded === '.'
      || decoded === '..'
      || decoded.includes('/')
      || decoded.includes('\\')
    ) {
      throw new Error('Invalid path segment');
    }

    return encodeURIComponent(decoded);
  });
};

const buildTargetUrl = (baseUrl: string, request: NextRequest, pathParts: string[]) => {
  const safePathParts = sanitizePathParts(pathParts);
  const path = `${safePathParts.join('/')}/`;
  const target = `${baseUrl}/${path}`;
  const url = new URL(target);
  url.search = request.nextUrl.search;
  return url.toString();
};

const buildErrorResponse = (status: number, message: string) => {
  const headers = new Headers({ 'content-type': 'application/json' });
  HOP_BY_HOP_HEADERS.forEach((header) => headers.delete(header));
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers,
  });
};

const fetchWithTimeout = async (url: string, requestInit: RequestInit) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  try {
    return await fetch(url, {
      ...requestInit,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
};

const forwardRequest = async (request: NextRequest, { params }: RouteContext) => {
  let pathParts: string[] = [];
  try {
    const resolvedParams = await params;
    pathParts = resolvedParams.path || [];
  } catch {
    return buildErrorResponse(400, 'Invalid proxy path.');
  }

  const headers = new Headers(request.headers);
  HOP_BY_HOP_HEADERS.forEach((header) => headers.delete(header));
  headers.delete('accept-encoding');

  const hasBody = !['GET', 'HEAD'].includes(request.method.toUpperCase());
  const bodyBuffer = hasBody ? new Uint8Array(await request.arrayBuffer()) : undefined;

  const requestInit: RequestInit = {
    method: request.method,
    headers,
    body: hasBody ? bodyBuffer : undefined,
    redirect: 'follow',
    cache: 'no-store',
  };

  const { primary, fallback } = resolveBackendApiBaseUrls(request);
  const canUseFallback = Boolean(fallback) && RETRYABLE_METHODS.has(request.method.toUpperCase());

  let primaryUrl: string;
  let fallbackUrl: string;
  try {
    primaryUrl = buildTargetUrl(primary, request, pathParts);
    fallbackUrl = canUseFallback ? buildTargetUrl(fallback, request, pathParts) : primaryUrl;
  } catch {
    return buildErrorResponse(400, 'Invalid proxy path.');
  }

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetchWithTimeout(primaryUrl, requestInit);
  } catch (error: unknown) {
    console.error('Proxy upstream fetch failed for primary backend', error);
    if (!canUseFallback) {
      const name = (error as { name?: string })?.name;
      if (name === 'AbortError') {
        return buildErrorResponse(504, 'Upstream request timed out.');
      }
      return buildErrorResponse(502, 'Failed to reach upstream service.');
    }

    try {
      upstreamResponse = await fetchWithTimeout(fallbackUrl, requestInit);
    } catch (fallbackError: unknown) {
      console.error('Proxy upstream fetch failed for fallback backend', fallbackError);
      const fallbackName = (fallbackError as { name?: string })?.name;
      if (fallbackName === 'AbortError') {
        return buildErrorResponse(504, 'Upstream request timed out.');
      }
      return buildErrorResponse(502, 'Failed to reach upstream service.');
    }
  }

  if (upstreamResponse.status >= 500 && canUseFallback) {
    try {
      upstreamResponse = await fetchWithTimeout(fallbackUrl, requestInit);
    } catch (error: unknown) {
      console.error('Proxy fallback retry failed after primary 5xx response', error);
      const name = (error as { name?: string })?.name;
      if (name === 'AbortError') {
        return buildErrorResponse(504, 'Upstream request timed out.');
      }
      return buildErrorResponse(502, 'Failed to reach upstream service.');
    }
  }

  const responseHeaders = new Headers(upstreamResponse.headers);
  HOP_BY_HOP_HEADERS.forEach((header) => responseHeaders.delete(header));
  responseHeaders.delete('content-length');
  responseHeaders.delete('content-encoding');

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  });
};

export const GET = forwardRequest;
export const HEAD = forwardRequest;
export const POST = forwardRequest;
export const PUT = forwardRequest;
export const PATCH = forwardRequest;
export const DELETE = forwardRequest;
export const OPTIONS = forwardRequest;
