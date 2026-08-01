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

  // Wrap getUser() so a transient token-expiry / network blip doesn't
  // log the user out. Previously, an expired access token (1 hour TTL)
  // caused `getUser()` to return `user=null`, which the gate below would
  // turn into a hard redirect to `/login?next=…` — even though the user
  // still had a valid refresh token. That produced the
  // "kicked out to /login mid-session" bug. With this guard we only
  // redirect when the Supabase session is definitively gone.
  let authData: { user: unknown } | null = null;
  try {
    const result = await supabase.auth.getUser();
    authData = { user: result.data.user };
  } catch {
    // Token expired / network blip / parse error — fall through and let
    // the client AuthProvider refresh the session on hydration.
    authData = { user: null };
  }
  const pathname = request.nextUrl.pathname;

  // If there's ANY Supabase auth cookie present (token + refresh-token),
  // trust the client to refresh and resume the session. Only redirect
  // when the cookies are missing entirely (i.e. signed-out, not signed-in).
  // The cookie name is `sb-<project-ref>-auth-token` by default; refresh
  // tokens live in the chunked `...-auth-token.*` cookies.
  const cookies = request.cookies.getAll();
  const hasSupabaseAuthCookie = cookies.some((c) =>
    /^sb-.*-auth-token(?:-code-verifier)?$/.test(c.name)
    || /^sb-.*-auth-token\.\d+$/.test(c.name)
  );

  const isAuthenticated = !!authData?.user || hasSupabaseAuthCookie;

  if (isProtectedRoute(pathname) && !isAuthenticated) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('next', pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (pathname === '/admin' || pathname.startsWith('/admin/')) {
    // Admin routes MUST have a server-verified user — never let a
    // "refresh-pending" request into /admin. If we can see cookies
    // but the user object didn't materialise, send them to the login
    // page to recover so they don't see a flash of admin content.
    if (!authData?.user) {
      if (!hasSupabaseAuthCookie) {
        const loginUrl = new URL('/login', request.url);
        loginUrl.searchParams.set('next', pathname);
        return NextResponse.redirect(loginUrl);
      }
      // Cookies present but getUser() failed — let the page render an
      // admin gate client-side (useAuth in each admin page already
      // handles this with a "Checking admin access…" loader).
    } else if (!isAdminUser(authData.user as Parameters<typeof isAdminUser>[0])) {
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }
  }

  if (isAuthenticated && (pathname === '/login' || pathname === '/register' || pathname === '/forgot-password' || pathname === '/reset-password')) {
    const redirectPath = authData?.user ? (isAdminUser(authData.user as Parameters<typeof isAdminUser>[0]) ? '/admin' : '/dashboard') : '/dashboard';
    return NextResponse.redirect(new URL(redirectPath, request.url));
  }

  return response;
};
