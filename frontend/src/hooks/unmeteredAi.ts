/**
 * unmeteredAi — "is this user's AI use token-metered?" (contract C12).
 *
 * Pure (no React / network imports) so the Header token pill, /tokens,
 * /generate and unit tests share one rule. Re-exported from
 * `hooks/useTokenWallet`, the import path existing callers use.
 */

/** Plans whose AI use is not token-metered (backend PLAN_FEATURES.unlimited_ai). */
export const UNLIMITED_AI_PLANS: ReadonlySet<string> = new Set(['1_year', 'legacy', 'admin_grant']);

/** The token-balance fields the rule reads (`GET /auth/tokens/`). */
export interface UnmeteredWallet {
  is_admin?: boolean;
  /** True when the plan is not token-metered (sent by the balance endpoint). */
  unlimited_ai?: boolean;
}

/** The profile fields the rule reads (`useAuth().user`). */
export interface UnmeteredUser {
  is_admin?: boolean;
  is_staff?: boolean;
  subscription_info?: { plan?: string; is_active?: boolean } | null;
}

/**
 * True when AI calls are not token-metered for this user: admins, staff and
 * active unlimited-AI plans (the backend's consume_ai_token bypass,
 * ai_engine.views._is_unmetered_staff). Uses the wallet's `unlimited_ai`
 * when the API sends it, else the profile's subscription plan.
 */
export function isUnmeteredAi(
  wallet: UnmeteredWallet | null | undefined,
  user: UnmeteredUser | null | undefined,
): boolean {
  if (wallet?.is_admin || user?.is_admin || user?.is_staff) return true;
  if (typeof wallet?.unlimited_ai === 'boolean') return wallet.unlimited_ai;
  const sub = user?.subscription_info;
  return Boolean(sub?.is_active && sub.plan && UNLIMITED_AI_PLANS.has(sub.plan));
}
