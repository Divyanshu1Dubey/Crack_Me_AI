/**
 * consent.ts — Lightweight consent management for analytics scripts.
 *
 * CrackCMS is privacy-conscious (medical content + Indian / GDPR-mixed
 * audience). The default is conservative: only `essential` cookies and
 * analytics fires are loaded unless the visitor explicitly opts in via
 * the Cookie Policy banner.
 *
 * Categories:
 *   - essential:   always allowed (auth, theme, CSRF, single-device)
 *   - analytics:   GA4, SimpleAnalytics, Datadog, Microsoft Clarity
 *   - marketing:   PostHog (funnels / session replay), UTM persistence
 *
 * Stored as JSON in localStorage under `crackcms_consent_v1`. Defaults
 * to `{ essential: true, analytics: false, marketing: false }` on first
 * visit. The banner is shown by `<ConsentBanner />` once per visitor.
 */

export type ConsentCategory = 'essential' | 'analytics' | 'marketing';

export interface ConsentState {
    essential: true; // always true — by definition cannot be opt-out
    analytics: boolean;
    marketing: boolean;
    updated_at: string;
}

const STORAGE_KEY = 'crackcms_consent_v1';

export const DEFAULT_CONSENT: ConsentState = {
    essential: true,
    analytics: false,
    marketing: false,
    updated_at: '',
};

function isBrowser(): boolean {
    return typeof window !== 'undefined';
}

function read(): ConsentState | null {
    if (!isBrowser()) return null;
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as ConsentState;
        if (typeof parsed.analytics !== 'boolean') return null;
        return parsed;
    } catch {
        return null;
    }
}

function write(state: ConsentState): void {
    if (!isBrowser()) return;
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
        /* ignore quota */
    }
    // Notify in-page listeners (ConsentBanner + vendor init scripts)
    window.dispatchEvent(
        new CustomEvent<ConsentState>('crackcms:consent', { detail: state }),
    );
}

export const consent = {
    read,
    write,

    /** True if the user has ever made a decision (banner can be hidden). */
    hasDecision(): boolean {
        return read() != null;
    },

    /** Allow all categories (Accept All button). */
    acceptAll(): ConsentState {
        const next: ConsentState = {
            essential: true,
            analytics: true,
            marketing: true,
            updated_at: new Date().toISOString(),
        };
        write(next);
        return next;
    },

    /** Reject all non-essential (Reject All button). */
    rejectAll(): ConsentState {
        const next: ConsentState = {
            essential: true,
            analytics: false,
            marketing: false,
            updated_at: new Date().toISOString(),
        };
        write(next);
        return next;
    },

    /** Update a single category from the granular preferences UI. */
    update(category: ConsentCategory, value: boolean): ConsentState {
        const current = read() ?? DEFAULT_CONSENT;
        const next: ConsentState = {
            ...current,
            essential: true,
            [category]: value,
            updated_at: new Date().toISOString(),
        } as ConsentState;
        write(next);
        return next;
    },

    isAllowed(category: ConsentCategory): boolean {
        const s = read();
        if (!s) return false; // no decision = no non-essential
        if (category === 'essential') return true;
        return s[category] === true;
    },

    /** Wire up listeners for the consent-change event. */
    onChange(handler: (state: ConsentState) => void): () => void {
        if (!isBrowser()) return () => {};
        const cb = (e: Event) => {
            const detail = (e as CustomEvent<ConsentState>).detail;
            if (detail) handler(detail);
        };
        window.addEventListener('crackcms:consent', cb);
        return () => window.removeEventListener('crackcms:consent', cb);
    },

    /**
     * Push the current consent state to all vendor APIs so they can
     * honour the user's preferences immediately.
     */
    syncVendors(): void {
        if (!isBrowser()) return;
        const s = read() ?? DEFAULT_CONSENT;
        // GA4 — gtag('consent', 'update', {...})
        try {
            (window as Window & { gtag?: (...args: unknown[]) => void }).gtag?.(
                'consent',
                'update',
                {
                    analytics_storage: s.analytics ? 'granted' : 'denied',
                    ad_storage: 'denied',
                    ad_user_data: 'denied',
                    ad_personalization: 'denied',
                },
            );
        } catch {
            /* ignore */
        }
        // PostHog — opt-out via localStorage + opt_in/out
        try {
            const ph = (window as Window & { posthog?: { opt_in_capturing?: () => void; opt_out_capturing?: () => void } }).posthog;
            if (ph) {
                if (s.marketing) ph.opt_in_capturing?.();
                else ph.opt_out_capturing?.();
            }
        } catch {
            /* ignore */
        }
    },
};

export default consent;
