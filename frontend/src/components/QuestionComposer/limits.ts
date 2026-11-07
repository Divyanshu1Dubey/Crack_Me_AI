/**
 * limits.ts — how many MCQs one generation may ask for (backend: GenerateQuestionsView).
 *
 * Everyone may generate up to STANDARD_MAX_COUNT (10) questions per batch. Users whose AI is
 * unlimited — the 1-year plan, legacy lifetime and admin-granted plans, admins and staff
 * (`isUnmeteredAi`, the backend's consume_ai_token bypass) — may generate up to
 * PREMIUM_MAX_COUNT (20). The backend answers a larger batch from anyone else with
 * `402 {code: 'upgrade_required', feature: LARGE_BATCH_FEATURE}` before any token is charged;
 * the composer shows those counts locked and opens the upgrade modal instead.
 *
 * Pure (no React / network imports): tests/unit/question-generator-limits.test.ts.
 */
import { COUNT_OPTIONS } from './constants';

export const STANDARD_MAX_COUNT = 10;
export const PREMIUM_MAX_COUNT = 20;
/** Paywall feature label; the same string as the backend's 402 `feature`. */
export const LARGE_BATCH_FEATURE = 'Generate up to 20 MCQs at once';

/** Most questions one batch may ask for. */
export function maxGenerationCount(unlimitedAi: boolean): number {
  return unlimitedAi ? PREMIUM_MAX_COUNT : STANDARD_MAX_COUNT;
}

/** True when `count` needs the 1-year plan for this user. */
export function isCountLocked(count: number, unlimitedAi: boolean): boolean {
  return count > maxGenerationCount(unlimitedAi);
}

export interface CountOption {
  value: number;
  locked: boolean;
  label: string;
}

/** The "Questions" choices: counts above the user's limit are listed, marked as 1-year plan only. */
export function countOptions(unlimitedAi: boolean): CountOption[] {
  return COUNT_OPTIONS.map((value) => {
    const locked = isCountLocked(value, unlimitedAi);
    return { value, locked, label: locked ? `${value} · 1-year plan 🔒` : String(value) };
  });
}

/** True for the generator's "batch too large for your plan" answer (403 / 402 `upgrade_required`). */
export function isUpgradeRequired(error: unknown): boolean {
  const data = (error as { response?: { data?: unknown } } | null)?.response?.data;
  return Boolean(data && typeof data === 'object' && (data as { code?: unknown }).code === 'upgrade_required');
}
