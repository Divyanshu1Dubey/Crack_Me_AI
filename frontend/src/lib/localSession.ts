/**
 * Shared by lib/localAuth.ts (browser) and the Next.js middleware (edge):
 * which sign-in this build uses, and the presence cookies that let the
 * middleware gate protected routes when the app runs on its own tokens
 * instead of Supabase.
 *
 * NEXT_PUBLIC_AUTH_MODE (inlined at build time):
 *   supabase               Supabase (needs NEXT_PUBLIC_SUPABASE_URL + a key)
 *   local                  dev-only email/password (/api/auth/local/*, DEBUG backends)
 *   django                 Django-native sign-in (/api/auth/native/*, Google ID
 *                          tokens); the backend must run AUTH_PROVIDER=django
 *   unset / anything else  Supabase when its URL and key are set, otherwise
 *                          django: without Supabase keys the Supabase mode
 *                          cannot sign anyone in (and its middleware threw on
 *                          every request, MIDDLEWARE_INVOCATION_FAILED).
 *
 * "local" and "django" are the token modes: SimpleJWT access/refresh tokens in
 * localStorage (crack_local_access / crack_local_refresh) and the presence
 * cookies below. The cookies are navigation hints only, exactly like the
 * Supabase cookie-presence check: the Django API authenticates and authorises
 * every request with the bearer token.
 */
export const LOCAL_SESSION_COOKIE = 'crack_local_session';
export const LOCAL_ADMIN_COOKIE = 'crack_local_admin';

export type AuthBuildMode = 'supabase' | 'local' | 'django';

/** The sign-in this build uses (NEXT_PUBLIC_AUTH_MODE, read at call time so tests can switch it). */
export const authBuildMode = (): AuthBuildMode => {
  const raw = (process.env.NEXT_PUBLIC_AUTH_MODE || '').trim().toLowerCase();
  if (raw === 'local' || raw === 'django' || raw === 'supabase') return raw;
  // Direct process.env.NEXT_PUBLIC_* reads so Next.js inlines them (edge + browser).
  const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || '').trim();
  const supabaseKey = (
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  ).trim();
  return supabaseUrl && supabaseKey ? 'supabase' : 'django';
};

/** Dev-only local auth (NEXT_PUBLIC_AUTH_MODE=local). */
export const isLocalAuthBuild = (): boolean => authBuildMode() === 'local';

/** Django-native sign-in (NEXT_PUBLIC_AUTH_MODE=django). */
export const isDjangoAuthBuild = (): boolean => authBuildMode() === 'django';

/** Either token mode: no Supabase client is created, the tokens live in localStorage. */
export const isTokenAuthBuild = (): boolean => authBuildMode() !== 'supabase';
