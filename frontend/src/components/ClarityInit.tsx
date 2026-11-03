'use client';

/**
 * ClarityInit.tsx — Microsoft Clarity loader.
 *
 * - Injected ONLY after the visitor allows the `analytics` category (the
 *   loader used to render unconditionally, so every visitor was recorded
 *   before choosing and even after "Reject all").
 * - Idempotent: next/script dedupes by id and `__CRACKCMS_CLARITY_INIT__`
 *   marks the first load.
 * - Respects consent changes at runtime: revoking calls
 *   `clarity('consent', false)`, which stops cookie-based tracking.
 * - Falls back silently if NEXT_PUBLIC_CLARITY_PROJECT_ID is unset.
 */

import Script from 'next/script';
import { useEffect, useState } from 'react';
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
    const [allowed, setAllowed] = useState(false);

    useEffect(() => {
        if (!enabled) return;
        const apply = (state: ConsentState) => {
            const granted = state.analytics === true;
            setAllowed(granted);
            if (typeof window.clarity === 'function') {
                try {
                    window.clarity('consent', granted);
                } catch {
                    /* ignore */
                }
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
            id="ms-clarity-loader"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
                __html: `(function(c,l,a,r,i,t,y){
                    c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
                    t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
                    y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
                })(window, document, "clarity", "script", ${JSON.stringify(CLARITY_ID)});
                window.clarity("consent");
                window.__CRACKCMS_CLARITY_INIT__ = true;`,
            }}
        />
    );
}
