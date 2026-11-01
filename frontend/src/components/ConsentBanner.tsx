'use client';

/**
 * ConsentBanner.tsx — Minimal cookie/analytics consent banner.
 *
 * - Auto-hides once a decision is stored.
 * - Three buttons: Accept all / Reject all / Manage.
 * - Granular preferences (toggle analytics / marketing) inline.
 * - Persists decision to localStorage and fires `crackcms:consent` event.
 * - Can be reopened from anywhere (e.g. the cookie policy's "Manage cookie
 *   preferences" button) by dispatching `crackcms:open-consent`.
 *
 * Categories match lib/consent.ts exactly: `analytics` (GA4, Clarity,
 * Datadog RUM) and `marketing` (PostHog product analytics, Google AdSense
 * when enabled). The old banner showed a separate "Product analytics"
 * checkbox that was never saved, while the "Advertising" box silently
 * switched PostHog on as well.
 */

/** Event name other components dispatch to reopen the preferences panel. */
export const OPEN_CONSENT_EVENT = 'crackcms:open-consent';

import { useEffect, useState } from 'react';
import { consent, type ConsentState } from '@/lib/consent';
import { analytics } from '@/lib/analytics';
import { ShieldCheck, X } from 'lucide-react';
import Link from 'next/link';

export default function ConsentBanner() {
    const [mounted, setMounted] = useState(false);
    const [visible, setVisible] = useState(false);
    const [showManage, setShowManage] = useState(false);
    const [draft, setDraft] = useState<{ analytics: boolean; marketing: boolean }>({
        analytics: false,
        marketing: false,
    });

    useEffect(() => {
        setMounted(true);
        const reopen = () => {
            const current = consent.read();
            setDraft({ analytics: current?.analytics === true, marketing: current?.marketing === true });
            setShowManage(true);
            setVisible(true);
        };
        window.addEventListener(OPEN_CONSENT_EVENT, reopen);
        let t: ReturnType<typeof setTimeout> | undefined;
        if (!consent.hasDecision()) {
            // Slight delay so the banner doesn't fight LCP
            t = setTimeout(() => setVisible(true), 800);
        }
        return () => {
            window.removeEventListener(OPEN_CONSENT_EVENT, reopen);
            if (t) clearTimeout(t);
        };
    }, []);

    if (!mounted || !visible) return null;

    const accept = () => {
        const next = consent.acceptAll();
        setVisible(false);
        analytics.event('consent_update', { decision: 'accept_all', ...next });
    };
    const reject = () => {
        const next = consent.rejectAll();
        setVisible(false);
        analytics.event('consent_update', { decision: 'reject_all', ...next });
    };
    const saveManage = () => {
        // One write with both categories, exactly as ticked.
        const next: ConsentState = {
            essential: true,
            analytics: draft.analytics,
            marketing: draft.marketing,
            updated_at: new Date().toISOString(),
        };
        consent.write(next);
        setVisible(false);
        analytics.event('consent_update', { decision: 'granular', ...next });
    };

    return (
        <div
            role="dialog"
            aria-label="Cookie preferences"
            className="fixed inset-x-3 bottom-3 z-50 mx-auto max-w-3xl rounded-2xl border border-border bg-card/95 p-4 shadow-2xl backdrop-blur-md sm:p-5"
        >
            <div className="flex items-start gap-3">
                <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary sm:flex">
                    <ShieldCheck className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-sm font-bold text-foreground">
                            Cookies & analytics
                        </h3>
                        <button
                            onClick={reject}
                            aria-label="Dismiss consent banner"
                            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                        We use cookies to keep you signed in and remember your
                        preferences. Only with your permission do we measure
                        traffic and performance, record anonymised sessions to
                        fix bugs, or (if ads are enabled) show ads.
                        You can change your choice any time in the{' '}
                        <Link href="/cookie-policy" className="text-primary underline">
                            cookie policy
                        </Link>
                        .
                    </p>

                    {showManage ? (
                        <div className="mt-3 space-y-2 rounded-xl border border-border bg-muted/30 p-3">
                            <label className="flex items-start gap-2 text-xs">
                                <input
                                    type="checkbox"
                                    checked
                                    disabled
                                    className="mt-0.5 h-3.5 w-3.5"
                                />
                                <span>
                                    <strong className="text-foreground">Essential</strong>
                                    <span className="block text-muted-foreground">
                                        Sign-in, exam attempt integrity, single-device
                                        session.
                                    </span>
                                </span>
                            </label>
                            <label className="flex items-start gap-2 text-xs">
                                <input
                                    type="checkbox"
                                    checked={draft.analytics}
                                    onChange={(e) =>
                                        setDraft((d) => ({ ...d, analytics: e.target.checked }))
                                    }
                                    className="mt-0.5 h-3.5 w-3.5"
                                />
                                <span>
                                    <strong className="text-foreground">Analytics</strong>
                                    <span className="block text-muted-foreground">
                                        Google Analytics 4, Microsoft Clarity, Datadog RUM —
                                        page views, scroll depth, performance and masked
                                        session replay.
                                    </span>
                                </span>
                            </label>
                            <label className="flex items-start gap-2 text-xs">
                                <input
                                    type="checkbox"
                                    checked={draft.marketing}
                                    onChange={(e) =>
                                        setDraft((d) => ({ ...d, marketing: e.target.checked }))
                                    }
                                    className="mt-0.5 h-3.5 w-3.5"
                                />
                                <span>
                                    <strong className="text-foreground">Product analytics &amp; advertising</strong>
                                    <span className="block text-muted-foreground">
                                        PostHog funnels and retention cohorts; Google AdSense
                                        ads if we enable them.
                                    </span>
                                </span>
                            </label>
                        </div>
                    ) : null}

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                        <button
                            onClick={accept}
                            className="rounded-xl bg-primary px-4 py-2 text-xs font-bold text-primary-foreground hover:opacity-95"
                        >
                            Accept all
                        </button>
                        <button
                            onClick={reject}
                            className="rounded-xl border border-border bg-card px-4 py-2 text-xs font-bold text-foreground hover:bg-muted"
                        >
                            Reject all
                        </button>
                        {showManage ? (
                            <button
                                onClick={saveManage}
                                className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-700"
                            >
                                Save preferences
                            </button>
                        ) : (
                            <button
                                onClick={() => setShowManage(true)}
                                className="rounded-xl border border-border bg-card px-4 py-2 text-xs font-bold text-foreground hover:bg-muted"
                            >
                                Manage
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
