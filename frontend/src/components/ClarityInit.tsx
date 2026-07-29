'use client';

/**
 * ClarityInit.tsx — Microsoft Clarity loader.
 *
 * - Lazily injected after consent for `analytics`.
 * - Idempotent: re-injection is a no-op via `__CRACKCMS_CLARITY_INIT__`.
 * - Respects consent in real-time (off when analytics is revoked).
 * - Falls back silently if NEXT_PUBLIC_CLARITY_PROJECT_ID is unset.
 */

import Script from 'next/script';
import { useEffect } from 'react';
import { consent, type ConsentState } from '@/lib/consent';

declare global {
    interface Window {
        __CRACKCMS_CLARITY_INIT__?: boolean;
        clarity?: ((cmd: string, ...args: unknown[]) => void) & { q?: unknown[][] };
    }
}

const CLARITY_ID = process.env.NEXT_PUBLIC_CLARITY_PROJECT_ID || '';

export default function ClarityInit() {
    const enabled =
        Boolean(CLARITY_ID) &&
        (process.env.NODE_ENV === 'production' ||
            process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === 'true');

    useEffect(() => {
        if (!enabled) return;
        const apply = (state: ConsentState) => {
            if (state.analytics && typeof window.clarity === 'function') {
                try {
                    window.clarity('consent');
                } catch {
                    /* ignore */
                }
            }
        };
        const off = consent.onChange(apply);
        // Initial state
        const current = consent.read();
        if (current) apply(current);
        return off;
    }, [enabled]);

    if (!enabled || !CLARITY_ID) return null;

    return (
        <Script
            id="ms-clarity-loader"
            strategy="afterInteractive"
            // Inline so we can delay-load based on consent
            dangerouslySetInnerHTML={{
                __html: `(function(c,l,a,r,i,t,y){
                    c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
                    t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
                    y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
                })(window, document, "clarity", "script", "${CLARITY_ID}");
                window.__CRACKCMS_CLARITY_INIT__ = true;`,
            }}
        />
    );
}
