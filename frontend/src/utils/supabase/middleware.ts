import { createServerClient } from '@supabase/ssr';
import { type NextRequest, NextResponse } from 'next/server';
import { assertSupabaseConfig } from './config';

const PROTECTED_ROUTE_PREFIXES = [
  '/admin',
  '/dashboard',
  '/questions',
  '/tests',
  '/analytics',
  '/settings',
  '/tokens',
  '/feedback',
  '/bookmarks',
  '/flashcards',
  '/generate',
  '/ai-tutor',
  '/roadmap',
  '/leaderboard',
  '/simulator',
  '/textbooks',
  '/upload',
  '/trends',
];

const isProtectedRoute = (pathname: string) =>
  PROTECTED_ROUTE_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));

const parseAdminEmailAllowlist = () => {
  const candidates = [
    process.env.CONTROL_TOWER_ADMIN_EMAILS,
    process.env.BOOTSTRAP_ADMIN_EMAIL,
    process.env.NEXT_PUBLIC_CONTROL_TOWER_ADMIN_EMAILS,
    process.env.NEXT_PUBLIC_BOOTSTRAP_ADMIN_EMAIL,
  ];

  return new Set(
    candidates
      .filter(Boolean)
      .flatMap((raw) => String(raw).split(','))
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  );
};

const ADMIN_EMAIL_ALLOWLIST = parseAdminEmailAllowlist();

const isAdminUser = (
  user: {
    email?: string;
    app_metadata?: Record<string, unknown>;
    user_metadata?: Record<string, unknown>;
  } | null | undefined,
) => {
  if (!user) return false;
  const appMetadata = user.app_metadata || {};
  const userMetadata = user.user_metadata || {};
  const email = String(user.email || '').trim().toLowerCase();

  const metadataAdmin =
    String(appMetadata.is_admin || '').toLowerCase() === 'true'
    || String(appMetadata.role || '').toLowerCase() === 'admin'
    || String(userMetadata.is_admin || '').toLowerCase() === 'true'
    || String(userMetadata.role || '').toLowerCase() === 'admin';

  return metadataAdmin || (email ? ADMIN_EMAIL_ALLOWLIST.has(email) : false);
};

export const updateSession = async (request: NextRequest) => {
  const { supabaseUrl, supabaseKey } = assertSupabaseConfig('middleware');
  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  });

  const supabase = createServerClient(
    supabaseUrl,
    supabaseKey,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    },
  );

  const { data: authData } = await supabase.auth.getUser();
  const pathname = request.nextUrl.pathname;

  if (isProtectedRoute(pathname) && !authData.user) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('next', pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (pathname === '/admin' || pathname.startsWith('/admin/')) {
    if (!authData.user) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('next', pathname);
      return NextResponse.redirect(loginUrl);
    }

    if (!isAdminUser(authData.user)) {
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }
  }

  if (authData.user && (pathname === '/login' || pathname === '/register' || pathname === '/forgot-password' || pathname === '/reset-password')) {
    const redirectPath = isAdminUser(authData.user) ? '/admin' : '/dashboard';
    return NextResponse.redirect(new URL(redirectPath, request.url));
  }

  return response;
};
