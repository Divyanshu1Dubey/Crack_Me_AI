'use client';

/**
 * AdSense component — renders a Google AdSense ad slot.
 *
 * Usage:
 *   <AdSense slot="in-content" />
 *   <AdSense slot="sidebar" />
 *   <AdSense slot="leaderboard" />
 *
 * Ad slots are loaded only after user consent for marketing cookies.
 * Falls back to an empty div on ad-blockers or before consent.
 */

import { useEffect, useState } from 'react';
import { consent } from '@/lib/consent';

interface AdSenseProps {
    slot: 'in-content' | 'sidebar' | 'leaderboard';
    className?: string;
}

const SLOT_CONFIG: Record<string, { className: string; placeholderText: string }> = {
    'in-content': {
        className: 'w-full max-w-3xl mx-auto my-6 min-h-[250px]',
        placeholderText: 'Advertisement',
    },
    'sidebar': {
        className: 'w-full min-h-[250px]',
        placeholderText: 'Advertisement',
    },
    'leaderboard': {
        className: 'w-full max-w-7xl mx-auto my-4 min-h-[90px]',
        placeholderText: 'Advertisement',
    },
};

export default function AdSense({ slot, className }: AdSenseProps) {
    const [shouldLoad, setShouldLoad] = useState(false);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        // Check consent on mount — load ads only if marketing consent granted
        if (consent.isAllowed('marketing')) {
            setShouldLoad(true);
        }
        // Listen for consent changes
        const unsub = consent.onChange((state) => {
            if (state.marketing && !shouldLoad) {
                setShouldLoad(true);
            }
        });
        return unsub;
    }, []);

    // Inject AdSense script once (global side-effect, guarded)
    useEffect(() => {
        if (typeof window === 'undefined') return;
        if ((window as any).__adsenseLoaded) return;
        const s = document.createElement('script');
        s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
        s.async = true;
        s.crossOrigin = 'anonymous';
        (document.head || document.body).appendChild(s);
        (window as any).__adsenseLoaded = true;
    }, []);

    if (!mounted) return null;

    const config = SLOT_CONFIG[slot] || SLOT_CONFIG['in-content'];

    return (
        <div className={`${config.className} ${className || ''}`}>
            {shouldLoad ? (
                <ins
                    className="adsbygoogle block"
                    style={{ display: 'block', textAlign: 'center' }}
                    data-ad-client="ca-pub-0000000000000000"
                    data-ad-slot={`cracklabs-${slot}`}
                    data-ad-format="auto"
                    data-full-width-responsive="true"
                />
            ) : (
                <div className="flex items-center justify-center min-h-[90px] bg-gray-100 dark:bg-slate-800 rounded text-xs text-gray-400 dark:text-slate-500">
                    {config.placeholderText}
                </div>
            )}
        </div>
    );
}
