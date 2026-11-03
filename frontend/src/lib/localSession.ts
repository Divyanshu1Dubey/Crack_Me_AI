/**
 * Shared by lib/localAuth.ts (browser) and the Next.js middleware (edge):
 * presence cookies that let the middleware gate protected routes when the
 * app runs with local auth (NEXT_PUBLIC_AUTH_MODE=local) instead of Supabase.
 *
 * They are navigation hints only, exactly like the Supabase cookie-presence
 * check in production: the Django API authenticates and authorises every
 * request with the bearer token.
 */
export const LOCAL_SESSION_COOKIE = 'crack_local_session';
export const LOCAL_ADMIN_COOKIE = 'crack_local_admin';

export const isLocalAuthBuild = (): boolean =>
  (process.env.NEXT_PUBLIC_AUTH_MODE || '').trim().toLowerCase() === 'local';
