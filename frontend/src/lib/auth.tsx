/**
 * auth.tsx — Authentication context provider for CrackCMS.
 * Provides useAuth() hook with: user, login, register, logout, loading state.
 * Uses Supabase sessions as the single auth source when Supabase is configured.
 * Wraps the entire app via AuthProvider in layout.tsx.
 */
'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { Provider, User as SupabaseUser } from '@supabase/supabase-js';
import {
    clearSupabaseLocalSession,
    getSupabaseBrowserClient,
    isInvalidRefreshTokenError,
    isSupabaseAuthEnabled,
} from './supabase';

interface User {
    id: number | string;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    role: string;
    is_admin?: boolean;
    target_exam: string;
}

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (identifier: string, password: string) => Promise<User>;
    magicLinkLogin: (email: string) => Promise<void>;
    oauthLogin: (provider: Provider) => Promise<void>;
    register: (data: Record<string, string>) => Promise<void>;
    logout: () => Promise<void>;
    refreshProfile: () => Promise<void>;
    isAuthenticated: boolean;
    isSupabaseAuth: boolean;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    loading: true,
    login: async () => {
        throw new Error('AuthProvider is not mounted');
    },
    magicLinkLogin: async () => undefined,
    oauthLogin: async () => undefined,
    register: async () => undefined,
    logout: async () => undefined,
    refreshProfile: async () => undefined,
    isAuthenticated: false,
    isSupabaseAuth: false,
});

const SUPABASE_AUTH_ENABLED = isSupabaseAuthEnabled();

const getBackendProfileUrl = () => {
    const configuredApiUrl = (process.env.NEXT_PUBLIC_API_URL || '').trim();
    if (configuredApiUrl) {
        return `${configuredApiUrl.replace(/\/+$/, '')}/auth/profile/`;
    }

    if (process.env.NODE_ENV === 'production') {
        return 'https://crackcms-vsthc.ondigitalocean.app/api/auth/profile/';
    }

    return 'http://localhost:8000/api/auth/profile/';
};

const fetchBackendProfile = async (accessToken: string) => {
    const response = await fetch(getBackendProfileUrl(), {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });

    if (!response.ok) {
        throw new Error(`Profile request failed with ${response.status}`);
    }

    return response.json();
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
    const isAdmin =
        String(appMetadata.is_admin || '').toLowerCase() === 'true' ||
        String(appMetadata.role || '').toLowerCase() === 'admin';
    const role = isAdmin ? 'admin' : String(metadata.role || 'student');

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
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
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
                    setUser(null);
                    setLoading(false);
                    return;
                }

                // Try to sync profile from backend (which has updated role from Supabase metadata)
                try {
                    const profileRes = await fetchBackendProfile(data.session.access_token);
                    if (!mounted) return;
                    setUser(profileRes);
                } catch {
                    // Fallback to mapped Supabase user
                    if (mounted) {
                        setUser(mapSupabaseUser(data.session.user));
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
                    setUser(null);
                    setLoading(false);
                }
            });

        // Subscribe to auth state changes
        const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
            if (!mounted) return;
            if (!session?.user) {
                setUser(null);
                return;
            }

            // Sync profile after auth state change
            fetchBackendProfile(session.access_token)
                .then((profileRes) => {
                    if (!mounted) return;
                    setUser(profileRes);
                })
                .catch(() => {
                    if (mounted) {
                        setUser(mapSupabaseUser(session.user));
                    }
                });
        });

        return () => {
            mounted = false;
            listener?.subscription.unsubscribe();
        };
    }, []);

    const login = async (identifier: string, password: string) => {
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('Authentication is not configured.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
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

            const profileRes = await fetchBackendProfile(accessToken);
            setUser(profileRes);
            return profileRes;
        } catch {
            // Fallback to mapped Supabase user if profile sync fails
            const mapped = mapSupabaseUser(signedInUser);
            setUser(mapped);
            return mapped;
        }
    };

    const register = async (formData: Record<string, string>) => {
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('Authentication is not configured.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
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
        if (data.session?.user) {
            try {
                const profileRes = await fetchBackendProfile(data.session.access_token);
                setUser(profileRes);
            } catch {
                setUser(mapSupabaseUser(data.session.user));
            }
        }
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

        const { error } = await supabase.auth.signInWithOtp({
            email: normalizedEmail,
            options: {
                emailRedirectTo: getAuthRedirectTo(),
                shouldCreateUser: false,
            },
        });
        if (error) throw new Error(error.message || 'Unable to send magic link.');
    };

    const oauthLogin = async (provider: Provider) => {
        if (!SUPABASE_AUTH_ENABLED) {
            throw new Error('OAuth is available only when Supabase auth is enabled.');
        }

        const supabase = getSupabaseBrowserClient();
        if (!supabase) {
            throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
        }

        const { error } = await supabase.auth.signInWithOAuth({
            provider,
            options: {
                redirectTo: getAuthRedirectTo(),
            },
        });
        if (error) throw new Error(error.message || `Unable to sign in with ${provider}.`);
    };

    const logout = async () => {
        const supabase = getSupabaseBrowserClient();
        try {
            await supabase?.auth.signOut();
        } catch (error) {
            console.error('Supabase sign out failed:', error);
        } finally {
            setUser(null);
        }
    };

    const refreshProfile = async () => {
        if (!SUPABASE_AUTH_ENABLED) return;

        const supabase = getSupabaseBrowserClient();
        if (!supabase) return;

        try {
            const { data } = await supabase.auth.getSession();
            const accessToken = data.session?.access_token;
            if (!accessToken) {
                throw new Error('Missing Supabase access token');
            }

            const profileRes = await fetchBackendProfile(accessToken);
            setUser(profileRes);
        } catch (error: unknown) {
            if (isInvalidRefreshTokenError(error)) {
                await clearSupabaseLocalSession();
            }
            // Fallback: try to get Supabase user
            try {
                const { data } = await supabase.auth.getUser();
                if (data.user) {
                    setUser(mapSupabaseUser(data.user));
                    return;
                }
            } catch {
                // Ignore fallback getUser errors and clear stale user state.
            }
            {
                setUser(null);
            }
        }
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
            isAuthenticated: !!user,
            isSupabaseAuth: SUPABASE_AUTH_ENABLED,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
