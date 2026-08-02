'use client';

/**
 * Paywall store (Task 8 of the freemium conversion layer).
 *
 * Simple React Context wrapper around the module-level singleton store
 * (`./paywallStore`). We don't pull in Zustand because there's only one
 * global piece of state and the api.ts interceptor needs to fire it from
 * outside React (see paywallStore.showPaywall / dismissPaywall).
 *
 * Anywhere in the app can call `usePaywall().show('AI Tutor')` to open
 * the global UpgradeModal; the modal is mounted once at the layout root.
 *
 * Feature strings intentionally match the backend `code: 'upgrade_required'`
 * payloads — see `backend/ai_engine/views.py`, `tests_engine/views.py`,
 * `questions/views.py` for the source of truth.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  showPaywall,
  dismissPaywall,
  subscribePaywall,
  getPaywallState,
} from './paywallStore';

export type { PaywallFeature, PaywallState } from './paywallStore';
import type { PaywallFeature, PaywallState } from './paywallStore';

const PaywallContext = createContext<{
  state: PaywallState;
  show: (feature: PaywallFeature, opts?: { remaining?: number | null; cap?: number | null }) => void;
  dismiss: () => void;
} | null>(null);

export function PaywallProvider({ children }: { children: React.ReactNode }) {
  // Read initial state synchronously so SSR + first render line up.
  const [state, setState] = useState<PaywallState>(() => getPaywallState());

  useEffect(() => {
    // Subscribe to the module store so the React tree re-renders when
    // the api.ts interceptor opens the modal. Avoids the React 19 lint
    // rule `react-hooks/set-state-in-effect` — the setState here only
    // fires on actual store mutations, not on every render.
    return subscribePaywall(setState);
  }, []);

  const show = useCallback(
    (feature: PaywallFeature, opts?: { remaining?: number | null; cap?: number | null }) =>
      showPaywall(feature, opts),
    [],
  );

  const dismiss = useCallback(() => dismissPaywall(), []);

  const value = useMemo(() => ({ state, show, dismiss }), [state, show, dismiss]);

  return <PaywallContext.Provider value={value}>{children}</PaywallContext.Provider>;
}

export function usePaywall() {
  const ctx = useContext(PaywallContext);
  if (!ctx) {
    throw new Error('usePaywall must be used within <PaywallProvider>');
  }
  return ctx;
}