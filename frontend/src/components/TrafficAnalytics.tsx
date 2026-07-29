'use client';

/**
 * TrafficAnalytics.tsx — Single source of truth for client-side analytics.
 *
 * Replaces the previous "fire page_view on every route change" component.
 * Now also handles:
 *   - scroll-depth bucketing (25/50/75/100)
 *   - time-on-page + visibility-change exit tracking
 *   - outbound link auto-tagging (data-track-outbound)
 *   - global JS error capture (filtered to user-actionable errors)
 *   - consent-aware vendor fan-out (gated by `consent.isAllowed`)
 *
 * Layout already injects GA4's gtag.js with `send_page_view: false`
 * so the page_view fired from here is the only one — no double counting.
 */

import { useEffect, useMemo, useRef } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import Script from 'next/script';
import { analytics } from '@/lib/analytics';
import { consent, type ConsentState } from '@/lib/consent';
import { classifyPath } from '@/lib/pageClassifier';

declare global {
    interface Window {
        dataLayer?: unknown[];
        gtag?: (...args: unknown[]) => void;
        sa_pageview?: () => void;
    }
}

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || 'G-MM88RT1QQK';
const SIMPLE_ANALYTICS_ENABLED = (process.env.NEXT_PUBLIC_SIMPLE_ANALYTICS_ENABLED ?? 'true') !== 'false';
const ANALYTICS_IN_DEV = (process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV ?? 'false') === 'true';

export default function TrafficAnalytics() {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const isEnabled = process.env.NODE_ENV === 'production' || ANALYTICS_IN_DEV;
    const shouldLoadGA = isEnabled && Boolean(GA_MEASUREMENT_ID);
    const shouldLoadSimpleAnalytics = isEnabled && SIMPLE_ANALYTICS_ENABLED;
    const lastSimpleAnalyticsPath = useRef<string | null>(null);

    const currentPath = useMemo(() => {
        if (!pathname) return '/';
        const query = searchParams?.toString();
        return query ? `${pathname}?${query}` : pathname;
    }, [pathname, searchParams]);

    /* ---- Page view ----------------------------------------------------- */
    useEffect(() => {
        if (!isEnabled) return;
        const classification = classifyPath(pathname || '/');
        const attr = analytics.attribution.attach({});
        analytics.pageView(currentPath, {
            ...(attr as Record<string, string | number | boolean>),
            page_type: classification.page_type,
            page_group: classification.page_group,
            exam_slug: classification.exam_slug ?? '',
            page_subject: classification.subject ?? '',
            page_topic: classification.topic ?? '',
            page_year: classification.year ?? '',
            page_blog_slug: classification.blog_slug ?? '',
            page_blog_category: classification.blog_category ?? '',
            page_guide_slug: classification.guide_slug ?? '',
        });
        consent.syncVendors();
    }, [currentPath, isEnabled, pathname]);

    /* ---- SimpleAnalytics hook (legacy, kept) --------------------------- */
    useEffect(() => {
        if (!shouldLoadSimpleAnalytics || typeof window === 'undefined') return;
        if (lastSimpleAnalyticsPath.current === null) {
            lastSimpleAnalyticsPath.current = currentPath;
            return;
        }
        if (
            lastSimpleAnalyticsPath.current !== currentPath &&
            typeof window.sa_pageview === 'function'
        ) {
            window.sa_pageview();
            lastSimpleAnalyticsPath.current = currentPath;
        }
    }, [currentPath, shouldLoadSimpleAnalytics]);

    /* ---- Scroll depth + time-on-page ----------------------------------- */
    useEffect(() => {
        if (!isEnabled) return;
        analytics.resetScroll();
        const onScroll = () => analytics.scrollDepth();
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => window.removeEventListener('scroll', onScroll);
    }, [currentPath, isEnabled]);

    /* ---- Outbound link capture (delegated) ----------------------------- */
    useEffect(() => {
        if (!isEnabled) return;
        const handler = (e: MouseEvent) => {
            const target = e.target as HTMLElement | null;
            if (!target) return;
            const anchor = target.closest('a');
            if (!anchor) return;
            const href = anchor.getAttribute('href');
            if (!href) return;
            // Auto-detect outbound (different origin)
            try {
                const url = new URL(href, window.location.href);
                if (url.host !== window.location.host) {
                    analytics.outbound(url.toString(), anchor.textContent?.trim() ?? '');
                }
            } catch {
                /* ignore malformed URLs */
            }
        };
        document.addEventListener('click', handler);
        return () => document.removeEventListener('click', handler);
    }, [isEnabled]);

    /* ---- Visibility / exit --------------------------------------------- */
    useEffect(() => {
        if (!isEnabled) return;
        const onVisibility = () => {
            if (document.visibilityState === 'hidden') {
                analytics.scrollDepth(true);
            }
        };
        document.addEventListener('visibilitychange', onVisibility);
        return () => document.removeEventListener('visibilitychange', onVisibility);
    }, [isEnabled]);

    /* ---- Global error capture ------------------------------------------ */
    useEffect(() => {
        if (!isEnabled) return;
        const onError = (e: ErrorEvent) => {
            // Filter common noise — favicon 404s, third-party widget warnings
            const msg = e.message || 'Unknown error';
            if (/favicon|sourcemap|ResizeObserver|Script error/i.test(msg)) return;
            analytics.error(msg.slice(0, 200), e.filename?.slice(0, 200) ?? 'unknown');
        };
        window.addEventListener('error', onError);
        return () => window.removeEventListener('error', onError);
    }, [isEnabled]);

    /* ---- Session start + return-visit detection ------------------------ */
    useEffect(() => {
        if (!isEnabled) return;
        analytics.sessionStart();
        return () => analytics.sessionStop();
    }, [isEnabled]);

    /* ---- Consent sync on mount ---------------------------------------- */
    useEffect(() => {
        const apply = (state: ConsentState) => {
            consent.syncVendors();
            // Resend identify if user has consented and we already have one
            if (state.analytics) {
                // No-op — vendor SDKs are now capturing. Identity flows from DatadogInit.
            }
        };
        const off = consent.onChange(apply);
        const existing = consent.read();
        if (existing) apply(existing);
        return off;
    }, []);

    if (!shouldLoadGA && !shouldLoadSimpleAnalytics) return null;

    return (
        <>
            {shouldLoadSimpleAnalytics && (
                <Script
                    id="simple-analytics"
                    data-collect-dnt="true"
                    src="https://scripts.simpleanalyticscdn.com/latest.js"
                    strategy="afterInteractive"
                />
            )}
        </>
    );
}
