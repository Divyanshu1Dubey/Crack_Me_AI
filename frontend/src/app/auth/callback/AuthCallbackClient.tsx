'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { EmailOtpType } from '@supabase/supabase-js';
import { getSupabaseBrowserClient } from '@/lib/supabase';
import { authAPI } from '@/lib/api';
import { consumePostAuthPath } from '@/lib/auth';
import { navigateAfterAuthChange } from '@/lib/authNavigation';
import { safeInternalPath } from '@/lib/auth-redirect';
import { isDjangoAuthBuild } from '@/lib/localSession';

// Django-native sign-in has no OAuth / email-link callback: the old Supabase
// links (sign-up confirmation, magic link, password recovery) land here and
// are sent to /login, with a hint when the URL carried one of them.
const OLD_LINK_MESSAGE =
  'This sign-in link is no longer valid. Please sign in with your email and password or with Google, or use "Forgot password?".';

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
    if (isDjangoAuthBuild()) {
      const next = safeInternalPath(searchParams.get('next'), '');
      const params = new URLSearchParams();
      if (next) params.set('next', next);
      const fragment = decodeUrlFragment();
      if (hasQueryParams || fragment.get('access_token') || fragment.get('error_description')) {
        params.set('authError', OLD_LINK_MESSAGE);
      }
      const query = params.toString();
      router.replace(query ? `/login?${query}` : '/login');
      return;
    }
    const finishAuth = async () => {
      const supabase = getSupabaseBrowserClient();
      if (!supabase) {
        router.replace('/login?authError=Supabase+is+not+configured');
        return;
      }

      try {
        const callbackError = searchParams.get('error_description') || searchParams.get('error');
        if (callbackError) {
          throw new Error(callbackError);
        }

        const code = searchParams.get('code');
        const tokenHash = searchParams.get('token_hash');
        const type = searchParams.get('type') as EmailOtpType | null;
        const nextPath = searchParams.get('next') || '';
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

        // Ensure callback verification produced a persisted session before redirecting.
        const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw sessionError;
        if (!sessionData.session) {
          const { data: refreshedSession, error: refreshError } = await supabase.auth.refreshSession();
          if (refreshError || !refreshedSession.session) {
            throw new Error('Magic link could not create a valid session. Check Supabase redirect URL settings.');
          }
        }

        // Destination remembered by auth.tsx before the OAuth / email-link
        // redirect (read now so it is cleared either way).
        const rememberedPath = consumePostAuthPath();
        const isRecovery = type === 'recovery' || fragment.get('type') === 'recovery';

        setStatusText('Loading your profile...');
        let isAdmin = false;
        try {
          const profile = (await authAPI.getProfile()).data as { is_admin?: boolean; role?: string } | undefined;
          isAdmin = profile?.is_admin === true || String(profile?.role || '').toLowerCase() === 'admin';
        } catch {
          // Profile fetch failed, but continue with redirect
        }

        // Explicit ?next=, then a password-recovery link, then the page the
        // user started from; otherwise students go to the dashboard and only
        // admins (per the backend profile) to /admin. Everyone used to be
        // sent to /admin, which bounced students and dropped deep links.
        const destination =
          safeInternalPath(nextPath, '')
          || (isRecovery ? '/reset-password' : '')
          || rememberedPath
          || (isAdmin ? '/admin' : '/dashboard');
        navigateAfterAuthChange(destination, { replace: true });
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
