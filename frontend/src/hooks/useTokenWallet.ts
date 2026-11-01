/**
 * useTokenWallet — read-only fetch of the current user's token balance.
 *
 * Why a custom hook: pages that surface "you have N tokens" need a
 * consistent shape and the same caching/retry policy. This hook
 * encapsulates that — a single SWR-style call wrapped with the project's
 * auth gating so unauthenticated users never trigger a 401.
 *
 * The backend (`GET /auth/tokens/`, accounts.serializers.TokenBalanceSerializer)
 * returns `{ available, purchased_tokens, feedback_credits, daily_tokens_used,
 * weekly_tokens_used, total_tokens_used, daily_limit, weekly_limit,
 * token_price, is_admin, unlimited_ai }` (`unlimited_ai`: the active plan is
 * not token-metered; `isUnmeteredAi` reads it). There is no `balance` field.
 *
 * Error is derived from SWR's error (not stored in local state) so the
 * hook doesn't need a `set-state-in-effect` to clear stale errors.
 */
'use client';

import useSWR from 'swr';
import { authAPI } from '@/lib/api';
import { useAuth } from '@/lib/auth';

export interface TokenWallet {
  /** Tokens the user can spend right now (free daily/weekly + credits + purchased). */
  available?: number;
  /** @deprecated Never sent by the balance endpoint; read `available`. */
  balance?: number;
  purchased_tokens?: number;
  feedback_credits?: number;
  daily_tokens_used?: number;
  weekly_tokens_used?: number;
  total_tokens_used?: number;
  daily_limit?: number;
  weekly_limit?: number;
  token_price?: number;
  is_admin?: boolean;
  /** True when the user's plan is not token-metered (PLAN_FEATURES.unlimited_ai). */
  unlimited_ai?: boolean;
}

// isUnmeteredAi(wallet, user): true for admins, staff and unlimited-AI plans
// (contract C12). It lives in a dependency-free module so it can be unit
// tested; re-exported here for existing callers.
export { isUnmeteredAi, UNLIMITED_AI_PLANS } from './unmeteredAi';
export type { UnmeteredUser, UnmeteredWallet } from './unmeteredAi';

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
