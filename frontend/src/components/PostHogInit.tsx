'use client';

/**
 * PostHogInit.tsx — PostHog product analytics loader.
 *
 * Loaded ONLY after the user grants `marketing` consent. We intentionally
 * use the snippet loader (no npm dep) so the bundle stays small and the
 * vendor script is fully tree-shaken when unused.
 *
 * Page-view capture is handled by PostHog's autoload, but custom events
 * flow through `analytics.event(...)` in `lib/analytics.ts`.
 */

import Script from 'next/script';
import { useEffect } from 'react';
import { consent, type ConsentState } from '@/lib/consent';

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

export default function PostHogInit() {
    const enabled =
        Boolean(POSTHOG_KEY) &&
        (process.env.NODE_ENV === 'production' ||
            process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === 'true');

    useEffect(() => {
        if (!enabled) return;
        // Honour consent flips at runtime
        const apply = (state: ConsentState) => {
            if (typeof window.posthog !== 'object') return;
            try {
                if (state.marketing) window.posthog.opt_in_capturing?.();
                else window.posthog.opt_out_capturing?.();
            } catch {
                /* ignore */
            }
        };
        const off = consent.onChange(apply);
        return off;
    }, [enabled]);

    if (!enabled || !POSTHOG_KEY) return null;

    return (
        <Script
            id="posthog-loader"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
                __html: `
                !function(t,e){var o,n,p,r;e.__SV=1.2.2;o=e.iml;var i=!1;e.posthog=e.posthog||function(){(e.posthog.q=e.posthog.q||[]).push(arguments)};r=e.posthog.q;for(;r.length&&(o=r.pop());)o();e.posthog.q=[];e.posthog.init=function(s,cfg,a){function d(t,e,o,a,n){for(var r=0;r<a.length;r++){var i=a[r];i[0]=t;i[1]=e;i[2]=(o||-1);i[3]=(n||"");}return p};n=["capture","identify","reset","opt_in_capturing","opt_out_capturing"];for(p=0;p<n.length;p++)e.posthog[n[p]]=d(n[p]);i=!0;if(a)e.posthog.init(s,a)};e.posthog.snippetLoaded=!0;var s=${JSON.stringify(POSTHOG_KEY)};e.posthog.init(s,${JSON.stringify({
                    api_host: POSTHOG_HOST,
                    capture_pageview: true,
                    capture_pageleave: true,
                    autocapture: true,
                    session_recording: {
                        recordCrossOriginIframes: false,
                        maskAllInputs: true,
                    },
                    respect_dnt: true,
                    disable_session_recording: true,
                })});
                window.__CRACKCMS_POSTHOG_INIT__ = true;
                `,
            }}
        />
    );
}