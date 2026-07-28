/**
 * useTokenWallet — read-only fetch of the current user's token balance.
 *
 * Why a custom hook: pages that surface "you have N tokens" need a
 * consistent shape and the same caching/retry policy. This hook
 * encapsulates that — a single SWR-style call wrapped with the project's
 * auth gating so unauthenticated users never trigger a 401.
 *
 * The backend returns `{ balance, daily_remaining, weekly_remaining,
 * is_admin, ... }` — see `accounts/views.py` for the exact shape.
 *
 * Error is derived from SWR's error (not stored in local state) so the
 * hook doesn't need a `set-state-in-effect` to clear stale errors.
 */
'use client';

import useSWR from 'swr';
import { authAPI } from '@/lib/api';
import { useAuth } from '@/lib/auth';

export interface TokenWallet {
  balance: number;
  daily_remaining?: number;
  weekly_remaining?: number;
  daily_quota?: number;
  weekly_quota?: number;
  is_admin?: boolean;
}

interface UseTokenWalletResult {
  wallet: TokenWallet | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<unknown>;
}

export function useTokenWallet(): UseTokenWalletResult {
  const { user, loading: authLoading } = useAuth();

  const swrKey = user ? '/auth/tokens/' : null;
  const fetcher = async () => {
    const res = await authAPI.getTokenBalance();
    return (res.data ?? null) as TokenWallet | null;
  };

  const { data, isLoading, mutate, error: swrError } = useSWR<TokenWallet | null>(
    swrKey,
    fetcher,
    {
      refreshInterval: 60_000,
      revalidateOnFocus: false,
    },
  );

  const errorMessage = swrError ? swrError.message ?? 'Token fetch failed' : null;

  return {
    wallet: data ?? null,
    loading: authLoading || isLoading,
    error: errorMessage,
    refresh: mutate,
  };
}