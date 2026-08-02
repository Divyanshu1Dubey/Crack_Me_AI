/**
 * paywallStore.ts — module-level singleton store for the paywall state.
 *
 * The api.ts response interceptor needs to open the upgrade modal from
 * *outside* React (it runs in Axios's promise chain), so a hook-based
 * `usePaywall().show(...)` won't work. We expose:
 *
 *   - `show(feature, opts?)` / `dismiss()` — imperative API for non-React
 *     callers (interceptors, event handlers).
 *   - `subscribe(listener)` — React-side subscription so the modal
 *     re-renders when state changes (see PaywallProvider).
 *
 * The single source of truth is the in-module `state` variable. The
 * React context (paywallContext.tsx) just mirrors this state via
 * `subscribe()` so the rest of the app can keep using the hook API.
 */

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

type Listener = (state: PaywallState) => void;

let state: PaywallState = {
  open: false,
  feature: 'Premium',
  remaining: null,
  cap: null,
};

const listeners = new Set<Listener>();

export function getPaywallState(): PaywallState {
  return state;
}

export function showPaywall(
  feature: PaywallFeature,
  opts?: { remaining?: number | null; cap?: number | null; message?: string | null },
): void {
  state = {
    open: true,
    feature,
    remaining: opts?.remaining ?? null,
    cap: opts?.cap ?? null,
  };
  for (const l of listeners) {
    try {
      l(state);
    } catch {
      /* swallow */
    }
  }
}

export function dismissPaywall(): void {
  if (!state.open) return;
  state = { ...state, open: false };
  for (const l of listeners) {
    try {
      l(state);
    } catch {
      /* swallow */
    }
  }
}

export function subscribePaywall(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}