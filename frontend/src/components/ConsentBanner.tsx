'use client';

/**
 * ConsentBanner.tsx — Minimal cookie/analytics consent banner.
 *
 * - Auto-hides once a decision is stored.
 * - Three buttons: Accept all / Reject all / Manage.
 * - Granular preferences (toggle analytics / marketing) inline.
 * - Persists decision to localStorage and fires `crackcms:consent` event.
 */

import { useEffect, useState } from 'react';
import { consent, type ConsentState } from '@/lib/consent';
import { analytics } from '@/lib/analytics';
import { ShieldCheck, X } from 'lucide-react';

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
        if (!consent.hasDecision()) {
            // Slight delay so the banner doesn't fight LCP
            const t = setTimeout(() => setVisible(true), 800);
            return () => clearTimeout(t);
        }
        return undefined;
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
        consent.update('analytics', draft.analytics);
        consent.update('marketing', draft.marketing);
        const next: ConsentState = {
            essential: true,
            analytics: draft.analytics,
            marketing: draft.marketing,
            updated_at: new Date().toISOString(),
        };
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
                        We use cookies to keep you signed in, remember your
                        preferences, and — only with your permission — measure
                        traffic so we can improve CrackCMS. You can change your
                        choice any time in the{' '}
                        <a href="/cookie-policy" className="text-primary underline">
                            cookie policy
                        </a>
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
                                        GA4, Microsoft Clarity — page views, scroll depth,
                                        performance.
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
                                    <strong className="text-foreground">Product analytics</strong>
                                    <span className="block text-muted-foreground">
                                        PostHog funnels, retention cohorts, session
                                        replay (for staff debugging).
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
