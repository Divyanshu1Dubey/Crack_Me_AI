'use client';

/**
 * PartnerAd: the non-Google ad network's units, isolated in a sandboxed iframe.
 *
 *   <PartnerAd kind="native" />      responsive native banner (in-content)
 *   <PartnerAd kind="skyscraper" />  160x300 banner (desktop sidebar)
 *
 * Security: sign-in tokens live in localStorage, so third-party ad code must never run in our
 * page. The unit's HTML (public/ads/*.html) loads in an iframe sandboxed WITHOUT
 * allow-same-origin: it runs in an opaque origin, can't read our cookies, localStorage or DOM,
 * and can't navigate the page (no allow-top-navigation). Clicks open a new tab
 * (allow-popups-to-escape-sandbox). The /ads/ pages get their own headers in vercel.json.
 *
 * Shown only on public content pages, next to the AdSense slots, and like AdSense only after
 * the visitor allowed the `marketing` consent category. Kill switch: NEXT_PUBLIC_PARTNER_ADS=off.
 *
 * Deliberately not used: the network's popunder and social-bar formats. They only work in the
 * top-level page (where they could read sign-in tokens), and they open windows / overlays.
 */
import { useEffect, useState } from 'react';
import { consent } from '@/lib/consent';

type Kind = 'native' | 'skyscraper';

const ENABLED = (process.env.NEXT_PUBLIC_PARTNER_ADS || 'on').trim().toLowerCase() !== 'off';

// Exported for tests: the sandbox must never grant same-origin or top navigation.
export const PARTNER_AD_SANDBOX = 'allow-scripts allow-popups allow-popups-to-escape-sandbox';

const UNITS: Record<Kind, { src: string; width?: number; height: number; wrapper: string }> = {
    native: { src: '/ads/native.html', height: 320, wrapper: 'w-full max-w-3xl mx-auto my-6' },
    skyscraper: { src: '/ads/banner-160x300.html', width: 160, height: 300, wrapper: 'hidden lg:flex flex-col items-center' },
};

export default function PartnerAd({ kind, className }: { kind: Kind; className?: string }) {
    const [allowed, setAllowed] = useState(false);

    useEffect(() => {
        if (!ENABLED) return;
        setAllowed(consent.isAllowed('marketing'));
        return consent.onChange((state) => setAllowed(state.marketing === true));
    }, []);

    if (!ENABLED || !allowed) return null;
    const unit = UNITS[kind];

    return (
        <div className={`${unit.wrapper} ${className || ''}`}>
            <span className="mb-1 block text-[10px] uppercase tracking-wide text-muted-foreground">Advertisement</span>
            <iframe
                src={unit.src}
                title="Advertisement"
                sandbox={PARTNER_AD_SANDBOX}
                loading="lazy"
                referrerPolicy="strict-origin-when-cross-origin"
                width={unit.width ?? '100%'}
                height={unit.height}
                style={{ border: 0, overflow: 'hidden', maxWidth: '100%' }}
            />
        </div>
    );
}
