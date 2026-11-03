/**
 * auth.tsx — Authentication context provider for CrackCMS.
 * Provides useAuth() hook with: user, login, register, logout, loading state.
 * The sign-in source is chosen at build time (NEXT_PUBLIC_AUTH_MODE,
 * lib/localSession.ts): Supabase sessions (default), the dev-only local
 * tokens ("local") or the Django-native sign-in ("django": email/password,
 * Google Identity Services, emailed confirmation / reset links; no Supabase
 * client is created).
 * Wraps the entire app via AuthProvider in layout.tsx.
 */
'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { AuthChangeEvent, Provider, User as SupabaseUser } from '@supabase/supabase-js';
import {
    clearSupabaseLocalSession,
    getSupabaseBrowserClient,
    isInvalidRefreshTokenError,
    isSupabaseAuthEnabled,
} from './supabase';
import {
    clearLocalTokens,
    fetchLocalProfile,
    getLocalAccessToken,
    googleSignIn,
    hasStoredTokenSession,
    isDjangoAuthMode,
    isLocalAuthMode,
    localLogin,
    localRegister,
    nativeLogin,
    nativeLogout,
    nativeRegister,
    requestPasswordReset,
    syncPresenceCookies,
    TOKEN_SESSION_ENDED_EVENT,
    type TokenAuthResult,
    watchTokenSession,
} from './localAuth';
import { authBuildMode, type AuthBuildMode } from './localSession';
import { googleSignInConfigured } from './googleIdentity';
import api, { getSessionEndingMessage } from './api';
import { safeInternalPath } from './auth-redirect';

interface SubscriptionInfo {
    plan: string;
    plan_display_name: string;
    status: string;
    is_active: boolean;
    starts_at: string | null;
    expires_at: string | null;
    days_remaining: number;
    amount_paid: number;
}

interface User {
    id: number | string;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    role: string;
    is_admin?: boolean;
    target_exam: string;
    phone?: string;
    college?: string;
    profile_bonus_rewarded?: boolean;
    is_subscribed?: boolean;
    scholarship_test_passed?: boolean;
    scholarship_test_attempts?: number;
    scholarship_granted_price?: number;
    subscription_info?: SubscriptionInfo | null;
    is_online?: boolean;
    // Freemium conversion layer (Task 9) — surfaced from /api/auth/profile/
    ai_tutor_used_today?: number;
    ai_tutor_daily_cap?: number | null;
    showcase_questions_remaining?: number | null;
    is_premium?: boolean;
    // Django-native sign-in (AUTH_PROVIDER=django): how this account can sign
    // in, and whether its email address is confirmed.
    auth_methods?: { password: boolean; google: boolean };
    email_verified?: boolean;
}

export type { User };

/** register() outcome: with Supabase "Confirm email" on there is no session yet. */
export interface RegisterResult {
    needsEmailConfirmation: boolean;
}

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (identifier: string, password: string) => Promise<User>;
    magicLinkLogin: (email: string) => Promise<void>;
    oauthLogin: (provider: Provider) => Promise<void>;
    register: (data: Record<string, string>) => Promise<RegisterResult>;
    logout: () => Promise<void>;
    refreshProfile: () => Promise<void>;
    /**
     * Imperatively merge a partial User patch into the current session state.
     *
     * Use this after a server-confirmed state change (e.g. a successful
     * Razorpay `/subscribe/verify/` response) to make the UI reflect the new
     * subscription immediately, without waiting for a full profile round-trip
     * that may transiently fail (5xx / network blip / failover).
     *
     * The merge preserves `id` and `email` from the existing user so the
     * session identity is never overwritten by a partial patch.
     */
    setUser: (updater: User | null | ((current: User | null) => User | null)) => void;
    resetPassword: (email: string) => Promise<void>;
    /** Django mode: sign in with the ID token from the Google Identity Services button. */
    googleLogin: (credential: string) => Promise<User>;
    /**
     * Django mode: adopt the session an emailed link signed in (verify email,
     * reset password, connect Google): load the profile and set the user.
     */
    completeTokenSignIn: (result: TokenAuthResult) => Promise<User>;
    isAuthenticated: boolean;
    isSupabaseAuth: boolean;
    /** Which sign-in this build uses (NEXT_PUBLIC_AUTH_MODE). */
    authMode: AuthBuildMode;
    /** Django mode with NEXT_PUBLIC_GOOGLE_CLIENT_ID set: show the Google button. */
    googleSignInEnabled: boolean;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    loading: true,
    login: async () => {
        throw new Error('AuthProvider is not mounted');
    },
    magicLinkLogin: async () => undefined,
    oauthLogin: async () => undefined,
    register: async () => {
        throw new Error('AuthProvider is not mounted');
    },
    logout: async () => undefined,
    refreshProfile: async () => undefined,
    setUser: () => undefined,
    resetPassword: async () => undefined,
    googleLogin: async () => {
        throw new Error('AuthProvider is not mounted');
    },
    completeTokenSignIn: async () => {
        throw new Error('AuthProvider is not mounted');
    },
    isAuthenticated: false,
    isSupabaseAuth: false,
    authMode: 'supabase',
    googleSignInEnabled: false,
});

const SUPABASE_AUTH_ENABLED = isSupabaseAuthEnabled();
// Dev-only: NEXT_PUBLIC_AUTH_MODE=local uses the backend's /auth/local/*
// endpoints instead of Supabase (see lib/localAuth.ts).
const LOCAL_AUTH_MODE = isLocalAuthMode();
// NEXT_PUBLIC_AUTH_MODE=django: the Django-native sign-in (/auth/native/*,
// /auth/google/*), the backend running AUTH_PROVIDER=django.
const DJANGO_AUTH_MODE = isDjangoAuthMode();
const AUTH_MODE = authBuildMode();
const GOOGLE_SIGN_IN_ENABLED = googleSignInConfigured();

/**
 * Fetch the backend profile (role, is_premium, subscription_info).
 *
 * Goes through the shared Axios client, so it gets the same base URL as
 * every other call (API proxy, localhost guard, unhealthy-host blacklist),
 * GET failover on 502/503/504, the X-Session-ID device header, the
 * session-ending codes (blocked account, logged-out device) and the
 * refresh-once-on-401 retry. It used to build its own URL with a hard-coded
 * production host and plain fetch(), so entitlements could come from a
 * different backend than the rest of the app.
 */
const fetchBackendProfile = async (accessToken: string): Promise<unknown> => {
    const response = await api.get('/auth/profile/', {
        headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.data;
};

// Several triggers ask for the profile of the same session at nearly the same
// time (the initial getSession(), the SIGNED_IN that supabase-js emits on load
// and on every tab focus, login()). Requests for the same access token share
// one fetch for a short window; a failed fetch is not reused.
const PROFILE_REUSE_MS = 30_000;
let recentProfileFetch: { token: string; at: number; promise: Promise<unknown> } | null = null;

/**
 * Supabase access tokens are short-lived (default 1 hour); an expired token
 * gets a 401 and the api.ts interceptor refreshes the session (bounded) and
 * retries once. `force` skips the reuse window (explicit refreshProfile()).
 */
const fetchBackendProfileWithRefresh = (accessToken: string, force = false): Promise<unknown> => {
    const now = Date.now();
    if (
        !force &&
        recentProfileFetch &&
        recentProfileFetch.token === accessToken &&
        now - recentProfileFetch.at < PROFILE_REUSE_MS
    ) {
        return recentProfileFetch.promise;
    }
    const promise = fetchBackendProfile(accessToken);
    const entry = { token: accessToken, at: now, promise };
    recentProfileFetch = entry;
    promise.catch(() => {
        if (recentProfileFetch === entry) recentProfileFetch = null;
    });
    return promise;
};

/**
 * Django mode: the backend profile of the stored session, through the same
 * Axios client (stored token, X-Session-ID -- the backend binds this browser's
 * device slot to the new session on this first request --, refresh-once-on-401
 * shared across tabs, the session-ending codes, GET failover).
 */
const fetchTokenProfile = (force = false): Promise<unknown> => {
    const token = getLocalAccessToken();
    if (token) return fetchBackendProfileWithRefresh(token, force);
    // Only a refresh token left: the 401 makes api.ts refresh and retry.
    return api.get('/auth/profile/').then((response) => response.data);
};

/** Django mode: did this profile failure end the session (vs a blip that keeps it)? */
const tokenSessionEnded = (error: unknown): boolean =>
    Boolean(getSessionEndingMessage(error)) || !hasStoredTokenSession();

// Django mode, first profile load: a 5xx / network blip is retried after these
// delays before the visitor is treated as signed out (the stored session is
// kept, so the next page load can still resume it).
const PROFILE_RETRY_DELAYS_MS = [1000, 3000];

const asProfileRecord = (profile: unknown): Record<string, unknown> | null =>
    profile && typeof profile === 'object' ? (profile as Record<string, unknown>) : null;

// Auth events after which the backend profile can differ. TOKEN_REFRESHED
// is deliberately absent: a new access token does not change the profile,
// and re-fetching on it looped with the api.ts refresh-on-401 whenever the
// backend rejected a valid session. INITIAL_SESSION is handled by the
// getSession() call in AuthProvider's effect.
const PROFILE_SYNC_EVENTS = new Set<AuthChangeEvent>(['SIGNED_IN', 'USER_UPDATED', 'PASSWORD_RECOVERY']);

// Where to land after an OAuth / email-link round trip. Stored locally
// rather than added to redirectTo, so the Supabase redirect allow-list
// (often an exact /auth/callback entry) keeps matching.
const POST_AUTH_PATH_KEY = 'crack_auth_next';
const POST_AUTH_PATH_MAX_AGE_MS = 60 * 60 * 1000;

const rememberPostAuthPath = (path?: string | null) => {
    if (typeof window === 'undefined') return;
    const requested = path ?? new URLSearchParams(window.location.search).get('next');
    const target = safeInternalPath(requested, '');
    try {
        if (target) {
            window.localStorage.setItem(POST_AUTH_PATH_KEY, JSON.stringify({ path: target, at: Date.now() }));
        } else {
            window.localStorage.removeItem(POST_AUTH_PATH_KEY);
        }
    } catch {
        // Storage blocked: the callback falls back to the default landing page.
    }
};

/** Read and clear the path remembered before an OAuth / magic-link / recovery redirect. */
export const consumePostAuthPath = (): string => {
    if (typeof window === 'undefined') return '';
    try {
        const raw = window.localStorage.getItem(POST_AUTH_PATH_KEY);
        window.localStorage.removeItem(POST_AUTH_PATH_KEY);
        if (!raw) return '';
        const { path, at } = JSON.parse(raw) as { path?: string; at?: number };
        if (typeof at !== 'number' || Date.now() - at > POST_AUTH_PATH_MAX_AGE_MS) return '';
        return safeInternalPath(path, '');
    } catch {
        return '';
    }
};

const getAuthRedirectTo = () => {
    if (typeof window !== 'undefined' && window.location?.origin) {
        return `${window.location.origin}/auth/callback`;
    }
    const configuredSiteUrl = (process.env.NEXT_PUBLIC_SITE_URL || '').trim();
    if (configuredSiteUrl) {
        return `${configuredSiteUrl.replace(/\/+$/, '')}/auth/callback`;
    }
    return 'http://localhost:3000/auth/callback';
};

const mapSupabaseUser = (supabaseUser: SupabaseUser): User => {
    const metadata = supabaseUser.user_metadata || {};
    const appMetadata = supabaseUser.app_metadata || {};
    const usernameFromEmail = supabaseUser.email?.split('@')[0] || 'student';
    const email = String(supabaseUser.email || '').trim().toLowerCase();

    // Fallback mapping, used only when the backend profile is unavailable.
    // Admin = a confirmed email on NEXT_PUBLIC_CONTROL_TOWER_ADMIN_EMAILS
    // (comma-separated) or Supabase app_metadata (`is_admin` / `role: admin`,
    // settable only with the service-role key). user_metadata is editable by
    // the user (supabase.auth.updateUser) and is NOT trusted, matching the
    // backend (accounts/supabase_rest_auth.py).
    const envEmails = (
        process.env.NEXT_PUBLIC_CONTROL_TOWER_ADMIN_EMAILS ||
        process.env.CONTROL_TOWER_ADMIN_EMAILS ||
        ''
    ).toLowerCase().split(',').map(e => e.trim()).filter(Boolean);

    const adminEmails = new Set(envEmails);

    const isAdmin =
        (adminEmails.has(email) && Boolean(supabaseUser.email_confirmed_at)) ||
        String(appMetadata.is_admin || '').toLowerCase() === 'true' ||
        String(appMetadata.role || '').toLowerCase() === 'admin';
    const role = isAdmin ? 'admin' : 'student';

    return {
        id: supabaseUser.id,
        username: String(metadata.username || usernameFromEmail),
        email: supabaseUser.email || '',
        first_name: String(metadata.first_name || ''),
        last_name: String(metadata.last_name || ''),
        role,
        is_admin: isAdmin,
        target_exam: String(metadata.target_exam || 'UPSC CMS'),
    };
};

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUserState] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (LOCAL_AUTH_MODE) {
            let mounted = true;
            fetchLocalProfile()
                .then((profile) => {
                    if (mounted) setUserState((profile as User | null) ?? null);
                })
                .catch(() => {
                    if (mounted) setUserState(null);
                })
                .finally(() => {
                    if (mounted) setLoading(false);
                });
            return () => {
                mounted = false;
            };
        }
        if (DJANGO_AUTH_MODE) {
            let mounted = true;
            const loadProfile = async () => {
                if (!hasStoredTokenSession()) {
                    syncPresenceCookies(null);
                    if (mounted) {
                        setUserState(null);
                        setLoading(false);
                    }
                    return;
                }
                for (let attempt = 0; ; attempt += 1) {
                    try {
                        const profile = await fetchTokenProfile(attempt > 0);
                        syncPresenceCookies(asProfileRecord(profile));
                        if (mounted) setUserState(profile as User);
                        break;
                    } catch (error: unknown) {
                        if (tokenSessionEnded(error) || attempt >= PROFILE_RETRY_DELAYS_MS.length) {
                            if (mounted) setUserState(null);
                            break;
                        }
                        await new Promise((resolve) => setTimeout(resolve, PROFILE_RETRY_DELAYS_MS[attempt]));
                        if (!mounted) return;
                    }
                }
                if (mounted) setLoading(false);
            };
            void loadProfile();

            // Other tabs: signed out there -> signed out here; signed in (or
            // into another account) there -> load that profile. A refreshed
            // token of the same account changes nothing.
            const stopWatching = watchTokenSession({
                onSignedOut: () => {
                    if (mounted) setUserState(null);
                },
                onAccountChanged: () => {
                    fetchTokenProfile(true)
                        .then((profile) => {
                            syncPresenceCookies(asProfileRecord(profile));
                            if (mounted) setUserState(profile as User);
                        })
                        .catch((error: unknown) => {
                            if (mounted && tokenSessionEnded(error)) setUserState(null);
                        });
                },
            });
            // This tab: the refresh token was refused for good (api.ts).
            const onSessionEnded = () => {
                if (mounted) setUserState(null);
            };
            window.addEventListener(TOKEN_SESSION_ENDED_EVENT, onSessionEnded);
            return () => {
                mounted = false;
                stopWatching();
                window.removeEventListener(TOKEN_SESSION_ENDED_EVENT, onSessionEnded);
            };
        }
        if (!SUPABASE_AUTH_ENABLED) {
            setLoading(false);
            return;
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            setLoading(false);
            return;
        }

        let mounted = true;

        // Initialize with current session
        supabase.auth
            .getSession()
            .then(async ({ data }) => {
                if (!mounted) return;
                if (!data.session?.user) {
                    setUserState(null);
                    setLoading(false);
                    return;
                }

                // Try to sync profile from backend (which has updated role from Supabase metadata)
                try {
                    const profileRes = await fetchBackendProfileWithRefresh(data.session.access_token);
                    if (!mounted) return;
                    setUserState(profileRes as User);
                } catch (error: unknown) {
                    // Fallback to mapped Supabase user -- unless the backend
                    // ended the session (blocked account, logged-out device):
                    // api.ts has already signed this browser out.
                    if (mounted) {
                        setUserState(getSessionEndingMessage(error) ? null : mapSupabaseUser(data.session.user));
                    }
                } finally {
                    if (mounted) setLoading(false);
                }
            })
            .catch(async (error: unknown) => {
                if (isInvalidRefreshTokenError(error)) {
                    await clearSupabaseLocalSession();
                }
                if (mounted) {
                    setUserState(null);
                    setLoading(false);
                }
            });

        // Subscribe to auth state changes
        const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
            if (!mounted) return;
            if (!session?.user) {
                setUserState(null);
                return;
            }
            if (!PROFILE_SYNC_EVENTS.has(event)) return;

            // Sync profile after sign-in / account changes (refresh-on-401 in api.ts)
            fetchBackendProfileWithRefresh(session.access_token, event === 'USER_UPDATED')
                .then((profileRes) => {
                    if (!mounted) return;
                    setUserState(profileRes as User);
                })
                .catch((error: unknown) => {
                    if (mounted) {
                        setUserState(getSessionEndingMessage(error) ? null : mapSupabaseUser(session.user));
                    }
                });
        });

        return () => {
            mounted = false;
            listener?.subscription.unsubscribe();
        };
    }, []);

    /**
     * Django mode: the tokens of a new session are stored (lib/localAuth.ts);
     * load the profile through the shared client, which also binds this
     * browser's device slot to the session (X-Session-ID).
     */
    const adoptTokenSession = async (result: TokenAuthResult): Promise<User> => {
        try {
            const profile = await fetchTokenProfile(true);
            syncPresenceCookies(asProfileRecord(profile));
            setUserState(profile as User);
            return profile as User;
        } catch (error: unknown) {
            const sessionEnded = getSessionEndingMessage(error);
            if (sessionEnded || !hasStoredTokenSession()) {
                setUserState(null);
                throw new Error(sessionEnded || 'Sign-in failed. Please try again.');
            }
            // A blip loading the profile: the sign-in answer carries it too.
            const fallback = result.user as unknown as User;
            setUserState(fallback);
            return fallback;
        }
    };

    const login = async (identifier: string, password: string) => {
        if (LOCAL_AUTH_MODE) {
            const result = await localLogin(identifier, password);
            const profile = ((await fetchLocalProfile()) ?? result.user) as unknown as User;
            setUserState(profile);
            return profile;
        }
        if (DJANGO_AUTH_MODE) {
            const email = (identifier || '').trim();
            if (!email.includes('@')) {
                throw new Error('Enter your email address to sign in.');
            }
            return adoptTokenSession(await nativeLogin(email, password));
        }
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('Authentication is not configured.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY).');
        }

        const normalizedIdentifier = (identifier || '').trim();
        if (!normalizedIdentifier.includes('@')) {
            throw new Error('Enter your email address to sign in.');
        }

        const { data, error } = await supabase.auth.signInWithPassword({
            email: normalizedIdentifier,
            password,
        });

        if (error) throw new Error(error.message || 'Login failed');

        const signedInUser = data.user || data.session?.user;
        if (!signedInUser) throw new Error('Login failed. Please try again.');

        // Sync profile from backend using the fresh Supabase access token.
        try {
            const accessToken = data.session?.access_token;
            if (!accessToken) {
                throw new Error('Missing Supabase access token');
            }

            const profileRes = await fetchBackendProfileWithRefresh(accessToken);
            setUserState(profileRes as User);
            return profileRes as User;
        } catch (error: unknown) {
            // Blocked account / unconfirmed email: api.ts signed this browser
            // out again; surface the reason on the login form.
            const sessionEnded = getSessionEndingMessage(error);
            if (sessionEnded) {
                setUserState(null);
                throw new Error(sessionEnded);
            }
            // Fallback to mapped Supabase user if profile sync fails
            const mapped = mapSupabaseUser(signedInUser);
            setUserState(mapped);
            return mapped;
        }
    };

    const register = async (formData: Record<string, string>): Promise<RegisterResult> => {
        if (LOCAL_AUTH_MODE) {
            const result = await localRegister(formData);
            setUserState(((await fetchLocalProfile()) ?? result.user) as unknown as User);
            return { needsEmailConfirmation: false };
        }
        if (DJANGO_AUTH_MODE) {
            // Always "check your email": the account is created when the
            // emailed /verify-email link is opened (the same answer whether
            // or not the address is taken).
            const { needsEmailConfirmation } = await nativeRegister(formData);
            return { needsEmailConfirmation };
        }
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('Authentication is not configured.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY).');
        }

        const email = (formData.email || '').trim();
        const password = formData.password || '';
        const username = (formData.username || '').trim();

        const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: {
                data: {
                    username,
                    first_name: (formData.first_name || '').trim(),
                    last_name: (formData.last_name || '').trim(),
                },
            },
        });

        if (error) throw new Error(error.message || 'Registration failed');
        if (!data.session?.user) {
            // Supabase "Confirm email" is on: no session until the link in
            // the confirmation email is opened.
            return { needsEmailConfirmation: true };
        }
        try {
            const profileRes = await fetchBackendProfileWithRefresh(data.session.access_token);
            setUserState(profileRes as User);
        } catch (profileError: unknown) {
            const sessionEnded = getSessionEndingMessage(profileError);
            if (sessionEnded) {
                setUserState(null);
                throw new Error(sessionEnded);
            }
            setUserState(mapSupabaseUser(data.session.user));
        }
        return { needsEmailConfirmation: false };
    };

    const magicLinkLogin = async (email: string) => {
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('Magic link is available only when Supabase auth is enabled.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
        }

        const normalizedEmail = email.trim();
        if (!normalizedEmail.includes('@')) {
            throw new Error('Enter a valid email address.');
        }

        rememberPostAuthPath();
        const { error } = await supabase.auth.signInWithOtp({
            email: normalizedEmail,
            options: {
                emailRedirectTo: getAuthRedirectTo(),
                shouldCreateUser: false,
            },
        });

        if (error) throw new Error(error.message || 'Magic link failed');
    };

    const resetPassword = async (email: string) => {
        if (LOCAL_AUTH_MODE) {
            throw new Error('Password reset is not available in local development mode. Use the seeded test accounts (see backend/.env.localdev).');
        }
        if (DJANGO_AUTH_MODE) {
            const address = email.trim();
            if (!address.includes('@')) {
                throw new Error('Enter a valid email address.');
            }
            // 202 for any address; the link (/reset-password#uid=..&token=..)
            // is mailed when an account has it. Also sets a first password
            // for accounts that only used Google.
            await requestPasswordReset(address);
            return;
        }
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('Password reset is available only when Supabase auth is enabled.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured.');
        }

        const normalizedEmail = email.trim();
        if (!normalizedEmail.includes('@')) {
            throw new Error('Enter a valid email address.');
        }

        // The recovery link signs the user in on /auth/callback; send them on
        // to the page that sets the new password.
        rememberPostAuthPath('/reset-password');
        const { error } = await supabase.auth.resetPasswordForEmail(normalizedEmail, {
            redirectTo: getAuthRedirectTo(),
        });

        if (error) throw new Error(error.message || 'Failed to send password reset email.');
    };

    const oauthLogin = async (provider: Provider) => {
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('OAuth is available only when Supabase auth is enabled.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
        }

        rememberPostAuthPath();
        const { error } = await supabase.auth.signInWithOAuth({
            provider,
            options: {
                redirectTo: getAuthRedirectTo(),
            },
        });
        if (error) throw new Error(error.message || `Unable to sign in with ${provider}.`);
    };

    const googleLogin = async (credential: string): Promise<User> => {
        if (!DJANGO_AUTH_MODE) {
            throw new Error('Google sign-in is not available here.');
        }
        return adoptTokenSession(await googleSignIn(credential));
    };

    const completeTokenSignIn = (result: TokenAuthResult): Promise<User> => {
        if (!DJANGO_AUTH_MODE) {
            return Promise.reject(new Error('This sign-in link is not available here.'));
        }
        return adoptTokenSession(result);
    };

    const logout = async () => {
        if (LOCAL_AUTH_MODE) {
            clearLocalTokens();
            setUserState(null);
            return;
        }
        if (DJANGO_AUTH_MODE) {
            // Tokens go first (here and, via the storage event, in the other
            // tabs); the backend then ends the session (best effort).
            nativeLogout();
            setUserState(null);
            return;
        }
        const supabase = getSupabaseBrowserClient();
        try {
            // 'local' ends only this browser's session. The default scope
            // ('global') revoked every session, logging the user out on all
            // devices although 2-4 devices are allowed.
            await supabase?.auth.signOut({ scope: 'local' });
        } catch {
            // Silent fail in production — user state is cleared below
        } finally {
            setUserState(null);
        }
    };

    const refreshProfile = async () => {
        // BUG FIX: previously gated on SUPABASE_AUTH_ENABLED — if Supabase
        // was misconfigured on a deployed node, refreshProfile() was a no-op
        // and the user appeared unsubscribed forever. We now ALWAYS attempt
        // the profile fetch when there is a session, regardless of which
        // auth backend is enabled.
        if (LOCAL_AUTH_MODE) {
            const profile = await fetchLocalProfile();
            setUserState((current) => (profile as User | null) ?? current);
            return;
        }
        if (DJANGO_AUTH_MODE) {
            if (!hasStoredTokenSession()) {
                syncPresenceCookies(null);
                setUserState(null);
                return;
            }
            try {
                // Explicit refresh (e.g. after a payment): never reuse a recent fetch.
                const profile = await fetchTokenProfile(true);
                syncPresenceCookies(asProfileRecord(profile));
                setUserState(profile as User);
            } catch (error: unknown) {
                // Only a session that is definitively over clears the user; a
                // blip (5xx, 429, network) keeps it as is (AUTH-06).
                if (tokenSessionEnded(error)) setUserState(null);
            }
            return;
        }
        const supabase = getSupabaseBrowserClient();
        if (!supabase) return;

        let accessToken: string | undefined;
        try {
            const { data, error } = await supabase.auth.getSession();
            if (error) {
                if (isInvalidRefreshTokenError(error)) {
                    await clearSupabaseLocalSession();
                    setUserState(null);
                }
                return; // transient (e.g. offline): keep the current user
            }
            accessToken = data.session?.access_token;
        } catch (error: unknown) {
            if (isInvalidRefreshTokenError(error)) {
                await clearSupabaseLocalSession();
                setUserState(null);
            }
            return;
        }
        if (!accessToken) {
            setUserState(null); // signed out
            return;
        }

        try {
            // Explicit refresh (e.g. after a payment): never reuse a recent fetch.
            const profileRes = await fetchBackendProfileWithRefresh(accessToken, true);
            setUserState(profileRes as User);
        } catch (error: unknown) {
            // Clear the user only when the session is definitively over.
            if (isInvalidRefreshTokenError(error)) {
                await clearSupabaseLocalSession();
                setUserState(null);
                return;
            }
            if (getSessionEndingMessage(error)) {
                setUserState(null); // api.ts already signed this browser out
                return;
            }
            // SECURITY / UX (Fix #8, AUTH-06): a transient failure (5xx, 429,
            // network, cold start) keeps the current user as is. The old code
            // set free users to null first, so useRequireAuth bounced them to
            // /login mid-session (losing the deep link / an in-progress test)
            // every time the 5-minute auto-refresh hit a blip. Only when there
            // is no user yet, adopt the Supabase identity -- in one update.
            let fallback: User | null = null;
            try {
                const { data } = await supabase.auth.getUser();
                fallback = data.user ? mapSupabaseUser(data.user) : null;
            } catch {
                // Ignore fallback getUser errors.
            }
            setUserState((current) => current ?? fallback);
        }
    };

    /**
     * Public setUser: applies an imperative user-state patch from any
     * component, typically after a server-confirmed action (Razorpay verify,
     * token purchase, admin grant, etc.) where waiting on a full profile
     * round-trip would either:
     *   1. Leave the UI stale until next hard reload, or
     *   2. Transiently fail (5xx, network blip, base-URL failover) and
     *      silently demote a paying user to a free user.
     *
     * The patch is merged into the current user — id + email are preserved
     * so the session identity can never be overwritten by a partial response.
     * If `current` is null (no user yet) the patch is adopted as-is.
     */
    const setUser: AuthContextType['setUser'] = (updater) => {
        setUserState((current) => {
            const next = typeof updater === 'function'
                ? (updater as (c: User | null) => User | null)(current)
                : updater;
            if (!next) return next;
            // Preserve session identity. If the patch omits id/email, fall
            // back to the current user so they aren't blanked.
            return {
                ...current,
                ...next,
                id: next.id ?? current?.id,
                email: next.email ?? current?.email,
                username: next.username ?? current?.username,
            } as User;
        });
    };

    return (
        <AuthContext.Provider value={{
            user,
            loading,
            login,
            magicLinkLogin,
            oauthLogin,
            register,
            logout,
            refreshProfile,
            setUser,
            resetPassword,
            googleLogin,
            completeTokenSignIn,
            isAuthenticated: !!user,
            isSupabaseAuth: SUPABASE_AUTH_ENABLED,
            authMode: AUTH_MODE,
            googleSignInEnabled: GOOGLE_SIGN_IN_ENABLED,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
