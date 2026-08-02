'use client';

/**
 * useUpgradeModal hook (Task 8) — thin wrapper around the paywall context
 * so call sites read like `useUpgradeModal().show('AI Tutor')`. Re-exported
 * separately so component files don't have to import the context module
 * directly.
 */
import { usePaywall, type PaywallFeature } from './paywallContext';

export function useUpgradeModal() {
  const { state, show, dismiss } = usePaywall();
  return {
    isOpen: state.open,
    feature: state.feature,
    remaining: state.remaining,
    cap: state.cap,
    show: (feature: PaywallFeature, opts?: { remaining?: number | null; cap?: number | null }) =>
      show(feature, opts),
    dismiss,
  };
}