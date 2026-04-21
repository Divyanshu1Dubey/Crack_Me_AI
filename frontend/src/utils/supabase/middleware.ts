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

const isAdminUser = (user: { app_metadata?: Record<string, unknown> } | null | undefined) => {
  if (!user) return false;
  const appMetadata = user.app_metadata || {};
  return String(appMetadata.is_admin || '').toLowerCase() === 'true' || String(appMetadata.role || '').toLowerCase() === 'admin';
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
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return response;
};
