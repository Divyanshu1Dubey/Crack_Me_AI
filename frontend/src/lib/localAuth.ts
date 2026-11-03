/**
 * localAuth.ts — sign-in without Supabase: the two token modes.
 *
 * NEXT_PUBLIC_AUTH_MODE=local (dev only): email/password against
 * /api/auth/local/*, which the backend only mounts when DEBUG=True and
 * LOCAL_DEV_AUTH=1. Never used in production builds.
 *
 * NEXT_PUBLIC_AUTH_MODE=django (production without Supabase; the backend runs
 * AUTH_PROVIDER=django): /api/auth/native/* (email/password, sign-up with an
 * emailed confirmation link, refresh, logout, password change),
 * /api/auth/password-reset/* and /api/auth/google/* (Google ID tokens).
 * Every answer with tokens is `{access, refresh, session_id, user}`; errors
 * are `{detail, code}` (accounts/native_auth.py), thrown here as AuthApiError.
 *
 * Both modes keep SimpleJWT access/refresh tokens in localStorage
 * (crack_local_access / crack_local_refresh) and the presence cookies the
 * middleware gates on (lib/localSession.ts); the E2E suite seeds those keys.
 * Refreshes are shared across concurrent requests and tabs (tokenRefresh.ts).
 */
import { apiUrl } from './apiBase';
import { deviceIdHeader } from './deviceId';
import {
  isDjangoAuthBuild,
  isLocalAuthBuild,
  isTokenAuthBuild,
  LOCAL_ADMIN_COOKIE,
  LOCAL_SESSION_COOKIE,
} from './localSession';
import { browserRefreshLock, createTokenRefresher, type RefreshOutcome } from './tokenRefresh';

const ACCESS_KEY = 'crack_local_access';
const REFRESH_KEY = 'crack_local_refresh';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
// Django mode: longer than the 14-day sliding refresh token, renewed on every
// token write and profile load. Expiring before the session would send a
// signed-in visitor to /login; outliving it only costs one client-side check.
const DJANGO_COOKIE_MAX_AGE = 60 * 60 * 24 * 30;

export const isLocalAuthMode = isLocalAuthBuild;
export const isDjangoAuthMode = isDjangoAuthBuild;
/** local or django: tokens in localStorage, no Supabase client. */
export const isTokenAuthMode = isTokenAuthBuild;

/** Presence cookie read by the middleware to gate protected routes. */
const setPresenceCookie = (name: string, on: boolean) => {
  if (typeof document === 'undefined') return;
  if (!isDjangoAuthBuild()) {
    document.cookie = `${name}=${on ? '1' : ''}; Path=/; SameSite=Lax; Max-Age=${on ? COOKIE_MAX_AGE : 0}`;
    return;
  }
  const secure = typeof window !== 'undefined' && window.location?.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `${name}=${on ? '1' : ''}; Path=/; SameSite=Lax; Max-Age=${on ? DJANGO_COOKIE_MAX_AGE : 0}${secure}`;
};

const isAdminProfile = (user: Record<string, unknown> | null | undefined): boolean =>
  !!user && (user.is_admin === true || String(user.role || '').toLowerCase() === 'admin');

const storage = (): Storage | null => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

const readKey = (key: string): string | null => {
  try {
    return storage()?.getItem(key) ?? null;
  } catch {
    return null;
  }
};

export const getLocalAccessToken = (): string | null => readKey(ACCESS_KEY);

export const getLocalRefreshToken = (): string | null => readKey(REFRESH_KEY);

/** True while this browser holds tokens of a session (the access token may have expired). */
export const hasStoredTokenSession = (): boolean => Boolean(getLocalAccessToken() || getLocalRefreshToken());

export const setLocalTokens = (access: string, refresh?: string | null) => {
  const s = storage();
  if (!s) return;
  s.setItem(ACCESS_KEY, access);
  if (refresh) s.setItem(REFRESH_KEY, refresh);
  setPresenceCookie(LOCAL_SESSION_COOKIE, true);
};

export const clearLocalTokens = () => {
  setPresenceCookie(LOCAL_SESSION_COOKIE, false);
  setPresenceCookie(LOCAL_ADMIN_COOKIE, false);
  const s = storage();
  if (!s) return;
  s.removeItem(ACCESS_KEY);
  s.removeItem(REFRESH_KEY);
};

/** Keep the middleware's presence cookies in step with the loaded profile (`null`: signed out). */
export const syncPresenceCookies = (profile: Record<string, unknown> | null) => {
  if (profile && hasStoredTokenSession()) {
    setPresenceCookie(LOCAL_SESSION_COOKIE, true);
    setPresenceCookie(LOCAL_ADMIN_COOKIE, isAdminProfile(profile));
    return;
  }
  setPresenceCookie(LOCAL_SESSION_COOKIE, false);
  setPresenceCookie(LOCAL_ADMIN_COOKIE, false);
};

const postJson = async (path: string, body: unknown) => {
  const response = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  let data: Record<string, unknown> = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    const fieldErrors = Object.values(data)
      .flat()
      .filter((v) => typeof v === 'string') as string[];
    const message = (data.error as string) || (data.detail as string) || fieldErrors[0] || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
};

export interface LocalAuthResult {
  access: string;
  refresh: string;
  user: Record<string, unknown>;
}

export const localLogin = async (identifier: string, password: string): Promise<LocalAuthResult> => {
  const data = (await postJson('/auth/local/login/', { email: identifier.trim(), password })) as unknown as LocalAuthResult;
  setLocalTokens(data.access, data.refresh);
  setPresenceCookie(LOCAL_ADMIN_COOKIE, isAdminProfile(data.user));
  return data;
};

export const localRegister = async (form: Record<string, string>): Promise<LocalAuthResult> => {
  const data = (await postJson('/auth/local/register/', {
    email: (form.email || '').trim(),
    username: (form.username || '').trim(),
    password: form.password || '',
    first_name: (form.first_name || '').trim(),
    last_name: (form.last_name || '').trim(),
  })) as unknown as LocalAuthResult;
  setLocalTokens(data.access, data.refresh);
  return data;
};

// ── Native auth requests (django mode) ────────────────────────────────────

const NETWORK_ERROR_MESSAGE = 'Unable to reach authentication server. Please try again in 30-60 seconds.';
const AUTH_REQUEST_TIMEOUT_MS = 20_000;

/** A refused sign-in request: the backend's `code` (e.g. `invalid_credentials`), HTTP status and body. */
export class AuthApiError extends Error {
  readonly code?: string;
  readonly status: number;
  readonly data: Record<string, unknown>;

  constructor(message: string, status: number, data: Record<string, unknown> = {}, code?: string) {
    super(message);
    this.name = 'AuthApiError';
    this.status = status;
    this.data = data;
    this.code = code;
  }
}

interface AuthPostOptions {
  bearer?: string | null;
  keepalive?: boolean;
  withDeviceId?: boolean;
  timeoutMs?: number;
}

/** POST JSON; the HTTP status and parsed body. Rejects with AuthApiError(status 0) when the API cannot be reached. */
const postForStatus = async (
  path: string,
  body: unknown,
  options: AuthPostOptions = {},
): Promise<{ status: number; data: Record<string, unknown> }> => {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (options.withDeviceId) Object.assign(headers, deviceIdHeader());
  if (options.bearer) headers.Authorization = `Bearer ${options.bearer}`;
  const controller = typeof AbortController === 'undefined' ? null : new AbortController();
  const timer = controller ? setTimeout(() => controller.abort(), options.timeoutMs ?? AUTH_REQUEST_TIMEOUT_MS) : null;
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: 'POST',
      headers,
      body: JSON.stringify(body ?? {}),
      keepalive: options.keepalive,
      signal: controller?.signal,
    });
  } catch {
    throw new AuthApiError(NETWORK_ERROR_MESSAGE, 0, {}, 'network_error');
  } finally {
    if (timer) clearTimeout(timer);
  }
  let data: Record<string, unknown> = {};
  try {
    const parsed: unknown = await response.json();
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) data = parsed as Record<string, unknown>;
  } catch {
    data = {};
  }
  return { status: response.status, data };
};

const errorMessageFor = (status: number, data: Record<string, unknown>): string => {
  // 404: the backend does not run the Django-native sign-in (AUTH_PROVIDER is
  // not "django"), or this API version is older than the frontend.
  if (status === 404) return 'Sign-in is not available right now. Please try again later.';
  const detail = typeof data.detail === 'string' ? data.detail.trim() : '';
  if (detail) return detail;
  if (status === 429) return 'Too many attempts. Please wait a few minutes and try again.';
  if (status >= 500) return 'Something went wrong on our server. Please try again.';
  return `Request failed (${status})`;
};

const postAuth = async (path: string, body: unknown, options?: AuthPostOptions): Promise<Record<string, unknown>> => {
  const { status, data } = await postForStatus(path, body, options);
  if (status >= 200 && status < 300) return data;
  const code = typeof data.code === 'string' ? data.code : undefined;
  throw new AuthApiError(errorMessageFor(status, data), status, data, code);
};

/** Body of a native sign-in: the tokens of a new server-side session and the profile. */
export interface TokenAuthResult {
  access: string;
  refresh: string;
  session_id?: string;
  user: Record<string, unknown>;
  created?: boolean;
  password_reset?: boolean;
}

const asTokenResult = (data: Record<string, unknown>): TokenAuthResult => {
  if (typeof data.access !== 'string' || !data.access || typeof data.refresh !== 'string' || !data.refresh) {
    throw new AuthApiError('Sign-in failed. Please try again.', 200, data, 'invalid_response');
  }
  const user = data.user && typeof data.user === 'object' ? (data.user as Record<string, unknown>) : {};
  return { ...(data as unknown as TokenAuthResult), user };
};

/** Store a native session: tokens plus presence cookies (admin from the returned profile). */
export const storeTokenSession = (result: TokenAuthResult) => {
  setLocalTokens(result.access, result.refresh);
  setPresenceCookie(LOCAL_ADMIN_COOKIE, isAdminProfile(result.user));
};

const signIn = async (path: string, body: unknown): Promise<TokenAuthResult> => {
  const result = asTokenResult(await postAuth(path, body));
  storeTokenSession(result);
  return result;
};

/** POST /auth/native/login/ (email only; the backend refuses usernames). */
export const nativeLogin = (email: string, password: string): Promise<TokenAuthResult> =>
  signIn('/auth/native/login/', { email: email.trim(), password });

/** POST /auth/native/register/: always 202, the account is created when the emailed link is opened. */
export const nativeRegister = async (form: Record<string, string>): Promise<{ needsEmailConfirmation: boolean; detail: string }> => {
  const data = await postAuth('/auth/native/register/', {
    email: (form.email || '').trim(),
    username: (form.username || '').trim(),
    password: form.password || '',
    first_name: (form.first_name || '').trim(),
    last_name: (form.last_name || '').trim(),
  });
  return {
    needsEmailConfirmation: data.needs_email_confirmation !== false,
    detail: typeof data.detail === 'string' ? data.detail : '',
  };
};

/** POST /auth/native/resend-verification/ (always 202: it never says whether the address is known). */
export const resendVerificationEmail = async (email: string): Promise<string> => {
  const data = await postAuth('/auth/native/resend-verification/', { email: email.trim() });
  return typeof data.detail === 'string' ? data.detail : 'If this email needs confirming, we sent a new link.';
};

/**
 * POST /auth/native/verify-email/: the link's {uid, token} (existing account), or {token, password}
 * for a new sign-up -- the password chosen at sign-up, so that opening a mail never creates an account
 * with a password somebody else chose (backend codes `password_required` / `password_mismatch`).
 */
export const verifyEmailLink = (link: { token: string; uid?: string | null; password?: string }): Promise<TokenAuthResult> =>
  signIn(
    '/auth/native/verify-email/',
    link.uid ? { uid: link.uid, token: link.token } : { token: link.token, password: link.password ?? '' },
  );

/** POST /auth/password-reset/ (django mode: 202 for any address). */
export const requestPasswordReset = async (email: string): Promise<void> => {
  await postAuth('/auth/password-reset/', { email: email.trim() });
};

/** POST /auth/password-reset/confirm/: sets the password, ends every other session and signs in. */
export const confirmPasswordReset = (link: { uid: string; token: string; newPassword: string }): Promise<TokenAuthResult> =>
  signIn('/auth/password-reset/confirm/', { uid: link.uid, token: link.token, new_password: link.newPassword });

/** POST /auth/google/ with a Google Identity Services ID token. */
export const googleSignIn = (credential: string): Promise<TokenAuthResult> => signIn('/auth/google/', { credential });

/** POST /auth/google/confirm-link/ with the token of the emailed "connect Google" link. */
export const googleConfirmLink = (token: string): Promise<TokenAuthResult> =>
  signIn('/auth/google/confirm-link/', { token });

/**
 * Sign out: the tokens and presence cookies go first (this tab and, through
 * the storage event, the others), then the backend ends the session
 * (POST /auth/native/logout/, best effort; the device keeps its slot).
 */
export const nativeLogout = (): void => {
  const access = getLocalAccessToken();
  const refresh = getLocalRefreshToken();
  clearLocalTokens();
  if (!access && !refresh) return;
  void postForStatus('/auth/native/logout/', refresh ? { refresh } : {}, {
    bearer: access,
    keepalive: true,
    withDeviceId: true,
    timeoutMs: 8_000,
  }).catch(() => undefined);
};

// ── Refresh (both token modes) ───────────────────────────────────────────

let localRefresher: ((failedAccess?: string | null) => Promise<RefreshOutcome>) | null = null;
let nativeRefresher: ((failedAccess?: string | null) => Promise<RefreshOutcome>) | null = null;

const makeRefresher = (path: string, clearOnTransientFailure: boolean) =>
  createTokenRefresher({
    readTokens: () => ({ access: getLocalAccessToken(), refresh: getLocalRefreshToken() }),
    writeTokens: (access, refresh) => setLocalTokens(access, refresh),
    clearTokens: clearLocalTokens,
    postRefresh: (refresh) => postForStatus(path, { refresh }, { timeoutMs: 15_000 }),
    withLock: browserRefreshLock(),
    clearOnTransientFailure,
  });

/**
 * Django mode: a fresh access token after `failedAccess` got a 401, shared by
 * concurrent requests and tabs. A definitive refusal (expired, revoked,
 * blocked, logged-out device) clears the stored session; a network error or
 * 5xx keeps it (see tokenRefresh.ts).
 */
export const refreshAccessToken = (failedAccess: string | null = null): Promise<RefreshOutcome> => {
  if (!nativeRefresher) nativeRefresher = makeRefresher('/auth/native/refresh/', false);
  return nativeRefresher(failedAccess);
};

/** Local mode: exchange the stored refresh token for a new access token (any failure clears the session, as before). */
export const refreshLocalAccessToken = async (failedAccess: string | null = null): Promise<string | null> => {
  if (!localRefresher) localRefresher = makeRefresher('/auth/local/refresh/', true);
  const outcome = await localRefresher(failedAccess);
  return outcome.ok ? outcome.access : null;
};

/** Load the backend profile for the stored session (refreshing once on 401). Local mode. */
export const fetchLocalProfile = async (): Promise<Record<string, unknown> | null> => {
  let access = getLocalAccessToken();
  if (!access) {
    setPresenceCookie(LOCAL_SESSION_COOKIE, false);
    setPresenceCookie(LOCAL_ADMIN_COOKIE, false);
    return null;
  }
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetch(apiUrl('/auth/profile/'), {
      // X-Session-ID: the backend binds this browser's device to the session
      // on its first request; without it every sign-in took a device slot.
      headers: { Authorization: `Bearer ${access}`, ...deviceIdHeader() },
    });
    if (response.ok) {
      const profile = (await response.json()) as Record<string, unknown>;
      // Keep the middleware's presence cookies in step with the real session.
      setPresenceCookie(LOCAL_SESSION_COOKIE, true);
      setPresenceCookie(LOCAL_ADMIN_COOKIE, isAdminProfile(profile));
      return profile;
    }
    if (response.status !== 401 || attempt > 0) break;
    access = await refreshLocalAccessToken(access);
    if (!access) break;
  }
  return null;
};

// ── Other tabs ───────────────────────────────────────────────────────────

/** `user_id` claim of a SimpleJWT token, unverified: only to tell two accounts' tokens apart. */
export const tokenSubject = (token: string | null | undefined): string | null => {
  const part = typeof token === 'string' ? token.split('.')[1] : '';
  if (!part) return null;
  try {
    const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '='))) as { user_id?: unknown };
    return payload.user_id === undefined || payload.user_id === null ? null : String(payload.user_id);
  } catch {
    return null;
  }
};

/**
 * Follow sign-ins and sign-outs made in other tabs (the `storage` event, which
 * fires only in the OTHER tabs). A refreshed token of the same account is not
 * a change: re-loading the profile on every rotation would loop with the
 * refresh-on-401 of a backend that rejects the session.
 */
export const watchTokenSession = (handlers: { onSignedOut: () => void; onAccountChanged: () => void }): (() => void) => {
  if (typeof window === 'undefined') return () => undefined;
  let sessionArea: Storage | null = null;
  try {
    sessionArea = window.sessionStorage;
  } catch {
    sessionArea = null;
  }
  const listener = (event: StorageEvent) => {
    if (event.key !== null && event.key !== ACCESS_KEY && event.key !== REFRESH_KEY) return;
    if (sessionArea && event.storageArea === sessionArea) return; // only localStorage holds the tokens
    if (!hasStoredTokenSession()) {
      handlers.onSignedOut();
      return;
    }
    if (event.key === REFRESH_KEY) return;
    const now = tokenSubject(getLocalAccessToken());
    if (now && now !== tokenSubject(event.oldValue)) handlers.onAccountChanged();
  };
  window.addEventListener('storage', listener);
  return () => window.removeEventListener('storage', listener);
};

/** Fired on window when this tab's token session ended without a page change (refresh refused). */
export const TOKEN_SESSION_ENDED_EVENT = 'crack:token-session-ended';
