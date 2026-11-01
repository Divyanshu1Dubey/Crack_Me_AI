'use client';

/**
 * PostHogInit.tsx — PostHog product analytics loader.
 *
 * Loaded ONLY after the user grants `marketing` consent (it used to render
 * for every visitor). Uses the official PostHog snippet (no npm dep, see
 * posthogLoaderScript in lib/analytics.ts) so the bundle stays small.
 * Revoking consent later calls opt_out_capturing().
 *
 * Page-view capture is handled by PostHog's autoload, but custom events
 * flow through `analytics.event(...)` in `lib/analytics.ts`.
 */

import Script from 'next/script';
import { useEffect, useState } from 'react';
import { consent, type ConsentState } from '@/lib/consent';
import { posthogLoaderScript } from '@/lib/analytics';

declare global {
    interface Window {
        __CRACKCMS_POSTHOG_INIT__?: boolean;
        // Augment only — posthog is declared globally in lib/analytics.ts
        posthogSnippet?: (...args: unknown[]) => void;
    }
}

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY || '';
const POSTHOG_HOST =
    process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com';

const POSTHOG_OPTIONS = {
    api_host: POSTHOG_HOST,
    person_profiles: 'identified_only',
    capture_pageview: true,
    capture_pageleave: true,
    autocapture: true,
    session_recording: {
        recordCrossOriginIframes: false,
        maskAllInputs: true,
    },
    respect_dnt: true,
    disable_session_recording: true,
};

export default function PostHogInit() {
    const enabled =
        Boolean(POSTHOG_KEY) &&
        (process.env.NODE_ENV === 'production' ||
            process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === 'true');
    const [allowed, setAllowed] = useState(false);

    useEffect(() => {
        if (!enabled) return;
        // Honour the stored decision and consent flips at runtime
        const apply = (state: ConsentState) => {
            const granted = state.marketing === true;
            setAllowed(granted);
            if (typeof window.posthog !== 'object' || !window.posthog) return;
            try {
                if (granted) window.posthog.opt_in_capturing?.();
                else window.posthog.opt_out_capturing?.();
            } catch {
                /* ignore */
            }
        };
        const off = consent.onChange(apply);
        const current = consent.read();
        if (current) apply(current);
        return off;
    }, [enabled]);

    if (!enabled || !allowed) return null;

    return (
        <Script
            id="posthog-loader"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
                __html: `${posthogLoaderScript(POSTHOG_KEY, POSTHOG_OPTIONS)}window.__CRACKCMS_POSTHOG_INIT__ = true;`,
            }}
        />
    );
}
