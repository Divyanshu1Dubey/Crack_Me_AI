import { NextRequest } from 'next/server';

const DEFAULT_BACKEND_API_URL = 'https://crackcms-backend.onrender.com/api';

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

const buildTargetUrl = (baseUrl: string, request: NextRequest, pathParts: string[]) => {
  const path = pathParts.join('/');
  const target = `${baseUrl}/${path}`;
  const url = new URL(target);
  url.search = request.nextUrl.search;
  return url.toString();
};

const forwardRequest = async (request: NextRequest, { params }: RouteContext) => {
  const resolvedParams = await params;
  const pathParts = resolvedParams.path || [];

  const headers = new Headers(request.headers);
  HOP_BY_HOP_HEADERS.forEach((header) => headers.delete(header));

  const hasBody = !['GET', 'HEAD'].includes(request.method.toUpperCase());
  const textBody = hasBody ? await request.text() : undefined;

  const requestInit: RequestInit = {
    method: request.method,
    headers,
    body: hasBody && textBody ? textBody : undefined,
    redirect: 'follow',
    cache: 'no-store',
  };

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(buildTargetUrl(PRIMARY_BACKEND_API_BASE_URL, request, pathParts), requestInit);
  } catch {
    upstreamResponse = await fetch(buildTargetUrl(FALLBACK_BACKEND_API_BASE_URL, request, pathParts), requestInit);
  }

  if (
    upstreamResponse.status >= 500 &&
    PRIMARY_BACKEND_API_BASE_URL !== FALLBACK_BACKEND_API_BASE_URL
  ) {
    upstreamResponse = await fetch(buildTargetUrl(FALLBACK_BACKEND_API_BASE_URL, request, pathParts), requestInit);
  }

  const responseHeaders = new Headers(upstreamResponse.headers);
  HOP_BY_HOP_HEADERS.forEach((header) => responseHeaders.delete(header));

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
