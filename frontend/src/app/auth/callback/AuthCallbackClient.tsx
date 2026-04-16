'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { EmailOtpType } from '@supabase/supabase-js';
import { getSupabaseBrowserClient } from '@/lib/supabase';
import { authAPI } from '@/lib/api';

const decodeUrlFragment = () => {
  if (typeof window === 'undefined') return new URLSearchParams();
  const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash;
  return new URLSearchParams(hash);
};

export default function AuthCallbackClient() {
  const [statusText, setStatusText] = useState('Completing sign in...');
  const router = useRouter();
  const searchParams = useSearchParams();

  const hasQueryParams = useMemo(() => {
    return Boolean(
      searchParams.get('code')
      || searchParams.get('token_hash')
      || searchParams.get('type')
      || searchParams.get('access_token')
      || searchParams.get('refresh_token'),
    );
  }, [searchParams]);

  useEffect(() => {
    const finishAuth = async () => {
      const supabase = getSupabaseBrowserClient();
      if (!supabase) {
        router.replace('/login?authError=Supabase+is+not+configured');
        return;
      }

      try {
        const code = searchParams.get('code');
        const tokenHash = searchParams.get('token_hash');
        const type = searchParams.get('type') as EmailOtpType | null;
        const fragment = decodeUrlFragment();

        if (code) {
          const { error } = await supabase.auth.exchangeCodeForSession(code);
          if (error) throw error;
        } else if (tokenHash && type) {
          const { error } = await supabase.auth.verifyOtp({
            token_hash: tokenHash,
            type,
          });
          if (error) throw error;
        } else if (fragment.get('access_token')) {
          const access_token = fragment.get('access_token');
          const refresh_token = fragment.get('refresh_token');
          if (!access_token || !refresh_token) {
            throw new Error('Missing auth token payload in callback URL.');
          }
          const { error } = await supabase.auth.setSession({
            access_token,
            refresh_token,
          });
          if (error) throw error;
        }

        setStatusText('Loading your profile...');
        let isAdmin = false;
        try {
          const profileRes = await authAPI.getProfile();
          isAdmin = Boolean(profileRes.data?.is_admin || profileRes.data?.role === 'admin');
        } catch {
          isAdmin = false;
        }

        router.replace(isAdmin ? '/admin' : '/dashboard');
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Authentication callback failed.';
        router.replace(`/login?authError=${encodeURIComponent(message)}`);
      }
    };

    if (hasQueryParams || typeof window !== 'undefined') {
      void finishAuth();
    }
  }, [hasQueryParams, router, searchParams]);

  return (
    <div className="min-h-screen grid place-items-center bg-slate-50 dark:bg-slate-950 px-6">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 text-center shadow-lg">
        <h1 className="text-xl font-semibold text-foreground">Authenticating...</h1>
        <p className="mt-2 text-sm text-muted-foreground">{statusText}</p>
      </div>
    </div>
  );
}
