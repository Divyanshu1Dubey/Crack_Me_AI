'use client';

/**
 * AdSense component — renders a Google AdSense ad slot.
 *
 * Usage:
 *   <AdSense slot="in-content" />
 *   <AdSense slot="sidebar" />
 *   <AdSense slot="leaderboard" />
 *
 * Renders NOTHING unless all of these hold:
 *   1. a real publisher id is configured (NEXT_PUBLIC_ADSENSE_CLIENT =
 *      "ca-pub-" + 16 digits — the old hard-coded ca-pub-0000000000000000
 *      could never serve),
 *   2. a numeric ad-unit id exists for the slot
 *      (NEXT_PUBLIC_ADSENSE_SLOT_IN_CONTENT / _SIDEBAR / _LEADERBOARD),
 *   3. the visitor allowed the `marketing` consent category.
 * Only then is adsbygoogle.js fetched and the unit pushed. This removes the
 * empty grey "Advertisement" boxes and the pre-consent ad-script load.
 */

import { useEffect, useRef, useState } from 'react';
import { consent } from '@/lib/consent';

interface AdSenseProps {
    slot: 'in-content' | 'sidebar' | 'leaderboard';
    className?: string;
}

const ADSENSE_CLIENT = (process.env.NEXT_PUBLIC_ADSENSE_CLIENT || '').trim();

// Referenced literally so Next can inline each NEXT_PUBLIC_ value.
const SLOT_IDS: Record<AdSenseProps['slot'], string> = {
    'in-content': (process.env.NEXT_PUBLIC_ADSENSE_SLOT_IN_CONTENT || '').trim(),
    sidebar: (process.env.NEXT_PUBLIC_ADSENSE_SLOT_SIDEBAR || '').trim(),
    leaderboard: (process.env.NEXT_PUBLIC_ADSENSE_SLOT_LEADERBOARD || '').trim(),
};

const SLOT_CLASS: Record<AdSenseProps['slot'], string> = {
    'in-content': 'w-full max-w-3xl mx-auto my-6',
    sidebar: 'w-full',
    leaderboard: 'w-full max-w-7xl mx-auto my-4',
};

const isRealPublisherId = (id: string) => /^ca-pub-\d{16}$/.test(id) && !/^ca-pub-0+$/.test(id);

type AdsWindow = Window & { adsbygoogle?: unknown[]; __adsenseLoaded?: boolean };

export default function AdSense({ slot, className }: AdSenseProps) {
    const slotId = SLOT_IDS[slot];
    const configured = isRealPublisherId(ADSENSE_CLIENT) && /^\d+$/.test(slotId);
    const [allowed, setAllowed] = useState(false);
    const pushed = useRef(false);

    useEffect(() => {
        if (!configured) return;
        setAllowed(consent.isAllowed('marketing'));
        return consent.onChange((state) => setAllowed(state.marketing === true));
    }, [configured]);

    useEffect(() => {
        if (!configured || !allowed || pushed.current) return;
        const win = window as AdsWindow;
        if (!win.__adsenseLoaded) {
            const s = document.createElement('script');
            s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(ADSENSE_CLIENT)}`;
            s.async = true;
            s.crossOrigin = 'anonymous';
            (document.head || document.body).appendChild(s);
            win.__adsenseLoaded = true;
        }
        try {
            (win.adsbygoogle = win.adsbygoogle || []).push({});
            pushed.current = true;
        } catch {
            /* ad blockers */
        }
    }, [configured, allowed]);

    if (!configured || !allowed) return null;

    return (
        <div className={`${SLOT_CLASS[slot]} ${className || ''}`}>
            <ins
                className="adsbygoogle block"
                style={{ display: 'block', textAlign: 'center' }}
                data-ad-client={ADSENSE_CLIENT}
                data-ad-slot={slotId}
                data-ad-format="auto"
                data-full-width-responsive="true"
            />
        </div>
    );
}
