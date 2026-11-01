import { createServerClient } from '@supabase/ssr';
import { type NextRequest, NextResponse } from 'next/server';
import { assertSupabaseConfig } from './config';
import { isLocalAuthBuild, LOCAL_ADMIN_COOKIE, LOCAL_SESSION_COOKIE } from '@/lib/localSession';

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

const isAdminPath = (pathname: string) => pathname === '/admin' || pathname.startsWith('/admin/');

/** /login?next=<path + query>, so a deep link survives the sign-in. */
const loginRedirect = (request: NextRequest) => {
  const loginUrl = new URL('/login', request.url);
  loginUrl.searchParams.set('next', `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(loginUrl);
};

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

/**
 * Best-effort "is this an admin?" from the Supabase user, used only to pick
 * where an already signed-in visitor of /login lands. app_metadata can only
 * be set with the service-role key; user_metadata is editable by the user
 * (supabase.auth.updateUser) and is never trusted. Admins promoted in the app
 * (Django role) are not visible here at all -- access to /admin is decided by
 * the backend profile on the page, never by this function.
 */
const isAdminUser = (
  user: {
    email?: string;
    app_metadata?: Record<string, unknown>;
  } | null | undefined,
) => {
  if (!user) return false;
  const appMetadata = user.app_metadata || {};
  const email = String(user.email || '').trim().toLowerCase();

  const metadataAdmin =
    String(appMetadata.is_admin || '').toLowerCase() === 'true'
    || String(appMetadata.role || '').toLowerCase() === 'admin';

  return metadataAdmin || (email ? ADMIN_EMAIL_ALLOWLIST.has(email) : false);
};

// Local development (NEXT_PUBLIC_AUTH_MODE=local; the backend only accepts
// local logins with DEBUG on): there is no Supabase session, so gate on the
// presence cookies kept by lib/localAuth.ts. Like the Supabase cookie check
// below, this is a navigation guard only; the Django API authenticates and
// authorises every request. No Supabase call is made in this mode.
const localSessionGate = (request: NextRequest) => {
  const pathname = request.nextUrl.pathname;
  const signedIn = request.cookies.get(LOCAL_SESSION_COOKIE)?.value === '1';
  if (isProtectedRoute(pathname) && !signedIn) {
    return loginRedirect(request);
  }
  if (isAdminPath(pathname) && request.cookies.get(LOCAL_ADMIN_COOKIE)?.value !== '1') {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }
  return NextResponse.next();
};

export const updateSession = async (request: NextRequest) => {
  if (isLocalAuthBuild()) return localSessionGate(request);

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
    return loginRedirect(request);
  }

  // /admin: any signed-in user gets the page; the admin role is checked by
  // the page itself against the BACKEND profile (role / is_admin; every
  // admin page and layout redirects non-admins to /dashboard) and by every
  // admin API. The old gate here trusted Supabase user_metadata, which a
  // student can set with supabase.auth.updateUser, and it bounced admins
  // who were promoted in the app (Django role, no Supabase flag).
  // (Signed-out visitors were already sent to /login above: /admin is a
  // protected prefix.)

  // Signed-in users skip the sign-in pages. /reset-password is NOT one of
  // them: the recovery link signs the user in on /auth/callback and sends
  // them there to set the new password (updateUser needs that session).
  if (isAuthenticated && (pathname === '/login' || pathname === '/register' || pathname === '/forgot-password')) {
    const redirectPath = authData?.user ? (isAdminUser(authData.user as Parameters<typeof isAdminUser>[0]) ? '/admin' : '/dashboard') : '/dashboard';
    return NextResponse.redirect(new URL(redirectPath, request.url));
  }

  return response;
};
