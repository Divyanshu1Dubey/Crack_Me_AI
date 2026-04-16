/**
 * auth.tsx — Authentication context provider for CrackCMS.
 * Provides useAuth() hook with: user, login, register, logout, loading state.
 * Stores JWT tokens in localStorage; auto-refreshes on mount.
 * Wraps the entire app via AuthProvider in layout.tsx.
 */
'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authAPI } from './api';
import type { User as SupabaseUser } from '@supabase/supabase-js';
import { getSupabaseBrowserClient, isSupabaseAuthEnabled } from './supabase';

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
    register: (data: Record<string, string>) => Promise<void>;
    logout: () => void;
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
    register: async () => undefined,
    logout: () => undefined,
    refreshProfile: async () => undefined,
    isAuthenticated: false,
    isSupabaseAuth: false,
});

const SUPABASE_AUTH_ENABLED = isSupabaseAuthEnabled();

const mapSupabaseUser = (supabaseUser: SupabaseUser): User => {
    const metadata = supabaseUser.user_metadata || {};
    const usernameFromEmail = supabaseUser.email?.split('@')[0] || 'student';

    return {
        id: supabaseUser.id,
        username: String(metadata.username || usernameFromEmail),
        email: supabaseUser.email || '',
        first_name: String(metadata.first_name || ''),
        last_name: String(metadata.last_name || ''),
        role: 'student',
        is_admin: false,
        target_exam: 'UPSC CMS',
    };
};

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (SUPABASE_AUTH_ENABLED) {
            const supabase = getSupabaseBrowserClient();
            if (!supabase) {
                queueMicrotask(() => setLoading(false));
                return;
            }

            let mounted = true;

            supabase.auth
                .getSession()
                .then(async ({ data }) => {
                    if (!mounted) return;
                    if (!data.session?.user) {
                        setUser(null);
                        return;
                    }

                    try {
                        const profileRes = await authAPI.getProfile();
                        if (!mounted) return;
                        setUser(profileRes.data);
                    } catch {
                        setUser(mapSupabaseUser(data.session.user));
                    }
                })
                .finally(() => {
                    if (mounted) setLoading(false);
                });

            const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
                if (!mounted) return;
                if (!session?.user) {
                    setUser(null);
                    return;
                }

                authAPI
                    .getProfile()
                    .then((profileRes) => {
                        if (!mounted) return;
                        setUser(profileRes.data);
                    })
                    .catch(() => {
                        setUser(mapSupabaseUser(session.user));
                    });
            });

            return () => {
                mounted = false;
                listener.subscription.unsubscribe();
            };
        }

        const token = localStorage.getItem('access_token');
        if (token) {
            authAPI.getProfile()
                .then(res => setUser(res.data))
                .catch(() => {
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');
                })
                .finally(() => setLoading(false));
        } else {
            queueMicrotask(() => setLoading(false));
        }
    }, []);

    const login = async (identifier: string, password: string) => {
        if (SUPABASE_AUTH_ENABLED) {
            const supabase = getSupabaseBrowserClient();
            if (!supabase) {
                throw new Error('Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
            }

            const email = identifier.trim();
            if (!email.includes('@')) {
                throw new Error('Enter your email address to sign in.');
            }

            const { data, error } = await supabase.auth.signInWithPassword({
                email,
                password,
            });

            if (error) throw new Error(error.message || 'Login failed');

            const signedInUser = data.user || data.session?.user;
            if (!signedInUser) throw new Error('Login failed. Please try again.');

            try {
                const profileRes = await authAPI.getProfile();
                setUser(profileRes.data);
                return profileRes.data;
            } catch {
                const mapped = mapSupabaseUser(signedInUser);
                setUser(mapped);
                return mapped;
            }
        }

        const { data } = await authAPI.login({ username: identifier, password });
        const accessToken = data.tokens?.access ?? data.access;
        const refreshToken = data.tokens?.refresh ?? data.refresh;
        if (!accessToken || !refreshToken) {
            throw new Error('Login response did not include tokens.');
        }
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
        setUser(data.user);
        return data.user;
    };

    const register = async (formData: Record<string, string>) => {
        if (SUPABASE_AUTH_ENABLED) {
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
                    const profileRes = await authAPI.getProfile();
                    setUser(profileRes.data);
                } catch {
                    setUser(mapSupabaseUser(data.session.user));
                }
            }
            return;
        }

        const { data } = await authAPI.register(formData);
        const accessToken = data.tokens?.access ?? data.access;
        const refreshToken = data.tokens?.refresh ?? data.refresh;
        if (!accessToken || !refreshToken) {
            throw new Error('Registration response did not include tokens.');
        }
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
        setUser(data.user);
    };

    const logout = () => {
        if (SUPABASE_AUTH_ENABLED) {
            const supabase = getSupabaseBrowserClient();
            supabase?.auth.signOut();
            setUser(null);
            return;
        }

        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setUser(null);
    };

    const refreshProfile = async () => {
        if (SUPABASE_AUTH_ENABLED) {
            const supabase = getSupabaseBrowserClient();
            if (!supabase) return;
            const { data } = await supabase.auth.getUser();
            setUser(data.user ? mapSupabaseUser(data.user) : null);
            return;
        }

        try {
            const res = await authAPI.getProfile();
            setUser(res.data);
        } catch { /* ignore */ }
    };

    return (
        <AuthContext.Provider value={{
            user,
            loading,
            login,
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
