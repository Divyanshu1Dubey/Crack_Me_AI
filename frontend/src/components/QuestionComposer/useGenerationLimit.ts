/**
 * useGenerationLimit — the signed-in user's question-generator batch limit (see limits.ts).
 *
 * Unlimited AI (`isUnmeteredAi`: the token wallet's `unlimited_ai`, else the profile's plan; admins
 * and staff) allows 20 questions per batch and costs no tokens; everyone else gets 10 per batch for
 * GENERATION_TOKEN_COST tokens. The wallet comes from the shared SWR cache (`useTokenWallet`).
 */
'use client';

import { useAuth } from '@/lib/auth';
import { isUnmeteredAi, useTokenWallet } from '@/hooks/useTokenWallet';
import { maxGenerationCount } from './limits';

export interface GenerationLimit {
  /** AI is not token-metered for this user (1-year / lifetime / admin-granted plan, admin, staff). */
  unlimitedAi: boolean;
  /** Most questions one batch may ask for. */
  maxCount: number;
}

export function useGenerationLimit(): GenerationLimit {
  const { user } = useAuth();
  const { wallet } = useTokenWallet();
  const unlimitedAi = isUnmeteredAi(wallet, user);
  return { unlimitedAi, maxCount: maxGenerationCount(unlimitedAi) };
}
