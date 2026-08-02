'use client';

/**
 * Paywall store (Task 8 of the freemium conversion layer).
 *
 * Simple React Context + reducer so we don't pull in another dependency
 * (no Zustand installed in this project). Anywhere in the app can call
 * `usePaywall().show('AI Tutor')` to open the global UpgradeModal; the
 * modal is mounted once at the layout root by `<PaywallRoot />`.
 *
 * Feature strings intentionally match the backend `code: 'upgrade_required'`
 * payloads — see `backend/ai_engine/views.py`, `tests_engine/views.py`,
 * `questions/views.py` for the source of truth.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
} from 'react';

export type PaywallFeature =
  | 'AI Tutor'
  | 'Mock Tests'
  | 'PYQ answers'
  | 'Full PYQ practice'
  | 'Deep Analytics'
  | string; // allow ad-hoc labels; backend is the source of truth

export interface PaywallState {
  open: boolean;
  feature: PaywallFeature;
  remaining: number | null;
  cap: number | null;
}

const initial: PaywallState = {
  open: false,
  feature: 'Premium',
  remaining: null,
  cap: null,
};

type Action =
  | { type: 'show'; feature: PaywallFeature; remaining?: number | null; cap?: number | null }
  | { type: 'dismiss' };

function reducer(state: PaywallState, action: Action): PaywallState {
  switch (action.type) {
    case 'show':
      return {
        open: true,
        feature: action.feature,
        remaining: action.remaining ?? null,
        cap: action.cap ?? null,
      };
    case 'dismiss':
      return { ...state, open: false };
    default:
      return state;
  }
}

const PaywallContext = createContext<{
  state: PaywallState;
  show: (feature: PaywallFeature, opts?: { remaining?: number | null; cap?: number | null }) => void;
  dismiss: () => void;
} | null>(null);

export function PaywallProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);

  const show = useCallback(
    (feature: PaywallFeature, opts?: { remaining?: number | null; cap?: number | null }) =>
      dispatch({ type: 'show', feature, remaining: opts?.remaining, cap: opts?.cap }),
    [],
  );

  const dismiss = useCallback(() => dispatch({ type: 'dismiss' }), []);

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