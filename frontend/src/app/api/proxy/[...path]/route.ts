import type { NextRequest } from 'next/server';
import { resolveBackendApiBaseUrls } from '../upstream';

const DEFAULT_TIMEOUT_MS = Number(process.env.PROXY_UPSTREAM_TIMEOUT_MS || 15000);
// Only these are replayed against the fallback after a failure: a POST or
// PATCH that hit a 5xx may already have been applied.
const RETRYABLE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

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

  // Local / LAN hosts and dev servers use the local backend (see upstream.ts).
  const { primary, fallback } = resolveBackendApiBaseUrls(request.nextUrl.hostname, {
    NODE_ENV: process.env.NODE_ENV,
    BACKEND_API_URL: process.env.BACKEND_API_URL,
    BACKEND_API_FALLBACK_URL: process.env.BACKEND_API_FALLBACK_URL,
  });
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
