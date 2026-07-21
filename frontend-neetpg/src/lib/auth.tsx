/**
 * auth.tsx — NEET PG site. Mirrors the CMS site's AuthProvider but with
 * the default target_exam set to "NEET PG" so signup metadata is correct.
 *
 * Shares the same Supabase project — sign-in via the CMS site works here
 * (and vice-versa) because SupabaseJWTAuthentication upserts by email.
 */
"use client";

import * as React from "react";
import { createContext, useContext, useEffect, useState } from "react";
import { jwtDecode } from "jwt-decode";
import { getSupabaseBrowserClient } from "./supabase";
import apiClient, { extractApiErrorMessage, setApiAccessToken } from "./api";

export interface AuthUser {
    id: string;
    email: string;
    fullName?: string;
    targetExam: string;
    isStaff?: boolean;
    subscriptionTier?: string;
}

interface AuthContextValue {
    user: AuthUser | null;
    loading: boolean;
    isAuthenticated: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, fullName: string) => Promise<void>;
    magicLinkLogin: (email: string) => Promise<void>;
    oauthLogin: (provider: "google") => Promise<void>;
    logout: () => Promise<void>;
    refreshProfile: () => Promise<void>;
    resetPassword: (email: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const DEFAULT_TARGET_EXAM = "NEET PG";

function getAuthRedirectTo(): string {
    if (typeof window === "undefined") return "/auth/callback";
    return `${window.location.origin}/auth/callback`;
}

async function fetchBackendProfile(accessToken: string): Promise<AuthUser | null> {
    try {
        const { data } = await apiClient.get("/auth/profile/", {
            headers: { Authorization: `Bearer ${accessToken}` },
        });
        return {
            id: String(data.id),
            email: data.email,
            fullName: data.full_name ?? data.name,
            targetExam: data.target_exam ?? DEFAULT_TARGET_EXAM,
            isStaff: Boolean(data.is_staff),
            subscriptionTier: data.subscription_tier ?? "free",
        };
    } catch {
        return null;
    }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const supabase = getSupabaseBrowserClient();
    const [user, setUser] = useState<AuthUser | null>(null);
    const [loading, setLoading] = useState(true);

    const refreshProfile = React.useCallback(async () => {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;
        if (!token) {
            setUser(null);
            setApiAccessToken(null);
            return;
        }
        setApiAccessToken(token);
        const profile = await fetchBackendProfile(token);
        setUser(profile);
    }, [supabase]);

    useEffect(() => {
        let cancelled = false;

        const init = async () => {
            try {
                const { data: sessionData } = await supabase.auth.getSession();
                if (cancelled) return;
                const token = sessionData.session?.access_token ?? null;
                setApiAccessToken(token);
                if (token) {
                    const profile = await fetchBackendProfile(token);
                    if (!cancelled) setUser(profile);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        init();

        const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
            const token = session?.access_token ?? null;
            setApiAccessToken(token);
            if (!token) {
                setUser(null);
                return;
            }
            fetchBackendProfile(token).then((profile) => {
                if (!cancelled) setUser(profile);
            });
        });

        return () => {
            cancelled = true;
            sub.subscription.unsubscribe();
        };
    }, [supabase]);

    const login = async (email: string, password: string) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw new Error(error.message);
    };

    const register = async (email: string, password: string, fullName: string) => {
        const { error } = await supabase.auth.signUp({
            email,
            password,
            options: {
                data: { full_name: fullName, target_exam: DEFAULT_TARGET_EXAM },
                emailRedirectTo: getAuthRedirectTo(),
            },
        });
        if (error) throw new Error(error.message);
    };

    const magicLinkLogin = async (email: string) => {
        const { error } = await supabase.auth.signInWithOtp({
            email,
            options: { emailRedirectTo: getAuthRedirectTo() },
        });
        if (error) throw new Error(error.message);
    };

    const oauthLogin = async (provider: "google") => {
        const { error } = await supabase.auth.signInWithOAuth({
            provider,
            options: { redirectTo: getAuthRedirectTo() },
        });
        if (error) throw new Error(error.message);
    };

    const logout = async () => {
        await supabase.auth.signOut();
        setUser(null);
        setApiAccessToken(null);
    };

    const resetPassword = async (email: string) => {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
            redirectTo: `${window.location.origin}/reset-password`,
        });
        if (error) throw new Error(error.message);
    };

    const value: AuthContextValue = {
        user,
        loading,
        isAuthenticated: Boolean(user),
        login,
        register,
        magicLinkLogin,
        oauthLogin,
        logout,
        refreshProfile,
        resetPassword,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
    return ctx;
}

// `jwtDecode` is kept available for legacy callers; suppress unused-import warning.
export const _jwtDecode = jwtDecode;
export const _extractApiErrorMessage = extractApiErrorMessage;
