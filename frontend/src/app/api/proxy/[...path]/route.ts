import { NextRequest } from 'next/server';

const DEFAULT_BACKEND_API_URL = 'https://crackcms-backend.onrender.com/api';
const DEFAULT_TIMEOUT_MS = Number(process.env.PROXY_UPSTREAM_TIMEOUT_MS || 15000);

const normalizeApiBaseUrl = (url: string) => {
  const normalized = url.replace(/\/+$/, '');
  return normalized.endsWith('/api') ? normalized : `${normalized}/api`;
};

const PRIMARY_BACKEND_API_BASE_URL = normalizeApiBaseUrl(
  (process.env.BACKEND_API_URL || DEFAULT_BACKEND_API_URL).trim()
);
const FALLBACK_BACKEND_API_BASE_URL = normalizeApiBaseUrl(DEFAULT_BACKEND_API_URL);

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
  const trailingSlash = request.nextUrl.pathname.endsWith('/');
  const path = `${safePathParts.join('/')}${trailingSlash ? '/' : ''}`;
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

  let primaryUrl: string;
  let fallbackUrl: string;
  try {
    primaryUrl = buildTargetUrl(PRIMARY_BACKEND_API_BASE_URL, request, pathParts);
    fallbackUrl = buildTargetUrl(FALLBACK_BACKEND_API_BASE_URL, request, pathParts);
  } catch {
    return buildErrorResponse(400, 'Invalid proxy path.');
  }

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetchWithTimeout(primaryUrl, requestInit);
  } catch (error: unknown) {
    console.error('Proxy upstream fetch failed for primary backend', error);
    if (PRIMARY_BACKEND_API_BASE_URL === FALLBACK_BACKEND_API_BASE_URL) {
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

  if (
    upstreamResponse.status >= 500 &&
    PRIMARY_BACKEND_API_BASE_URL !== FALLBACK_BACKEND_API_BASE_URL
  ) {
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
