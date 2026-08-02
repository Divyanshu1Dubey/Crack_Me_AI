/**
 * analytics.ts — Centralised event-tracking surface for CrackCMS.
 *
 * Wraps four vendors behind a single typed API:
 *   - Google Analytics 4   (`window.gtag`)
 *   - Microsoft Clarity    (`window.clarity`)
 *   - PostHog              (`window.posthog`)
 *   - Datadog RUM          (`@datadog/browser-rum`)
 *
 * Design rules:
 *   1. Never throw — every helper is a safe no-op on SSR / when the vendor
 *      is unavailable / when consent is denied.
 *   2. Single event taxonomy across all vendors (`AnalyticsEvent`). Any
 *      new event MUST be added here, otherwise GA4 + PostHog + Clarity
 *      dashboards drift apart.
 *   3. Lazy / consent-gated — `loadConsent()` from `lib/consent` gates
 *      vendor script init. See `ConsentGate.tsx` for the runtime gate.
 *   4. No duplicate `page_view` fires — GA4 auto-pv is disabled in
 *      layout.tsx (`send_page_view: false`) and we push manually via
 *      `analytics.pageView(...)` from `TrafficAnalytics`.
 */

import type { User } from './auth';

declare global {
    interface Window {
        gtag?: (...args: unknown[]) => void;
        dataLayer?: unknown[];
        clarity?: ((cmd: string, ...args: unknown[]) => void) & { q?: unknown[][] };
        posthog?: {
            init: (key: string, opts: Record<string, unknown>) => void;
            capture: (event: string, properties?: Record<string, unknown>) => void;
            identify: (id: string, properties?: Record<string, unknown>) => void;
            reset: () => void;
            opt_in_capturing?: () => void;
            opt_out_capturing?: () => void;
            setPersonProperties?: (properties: Record<string, unknown>) => void;
            startSessionRecording?: () => void;
            stopSessionRecording?: () => void;
        };
        // Datadog RUM
        DD_RUM?: {
            addUserAction: (name: string, context?: Record<string, unknown>) => void;
            setUser: (user: Record<string, unknown>) => void;
            clearUser: () => void;
        };
    }
}

/* ----------------------------------------------------------------------- */
/* Event taxonomy                                                           */
/* ----------------------------------------------------------------------- */

export type AnalyticsEvent =
    /* Lifecycle */
    | 'page_view'
    | 'session_start'
    | 'engagement_time'
    | 'scroll_depth'
    | 'cta_click'
    | 'exit_intent'
    | 'bounce'
    | 'return_visit'
    | 'error'
    | 'consent_update'
    | 'ai_tutor_mode_switch'
    /* Auth */
    | 'sign_up'
    | 'login'
    | 'logout'
    | 'register_intent'
    /* Navigation / Search */
    | 'site_search'
    | 'search_result_click'
    | 'outbound_click'
    | 'internal_link_click'
    /* Blog */
    | 'blog_view'
    | 'blog_scroll_depth'
    | 'blog_read_complete'
    | 'blog_share'
    | 'blog_copy_link'
    | 'blog_comment'
    | 'blog_newsletter_signup'
    | 'blog_cta_click'
    /* Question bank / Practice */
    | 'question_view'
    | 'question_solve'
    | 'question_skip'
    | 'question_bookmark'
    | 'question_note_add'
    | 'ai_explanation_open'
    | 'ai_explanation_feedback'
    /* AI Tutor */
    | 'ai_tutor_open'
    | 'ai_tutor_conversation_start'
    | 'ai_tutor_message'
    | 'ai_tutor_feedback'
    /* Tests / Simulator */
    | 'mock_test_start'
    | 'mock_test_complete'
    | 'mock_test_abandon'
    | 'pyq_year_open'
    /* Subscription / Revenue */
    | 'subscription_intent'
    | 'checkout_start'
    | 'payment_success'
    | 'payment_failure'
    | 'coupon_applied'
    /* Paywall (freemium conversion layer — 2026-08-02) */
    | 'paywall_view'
    | 'upgrade_click'
    | 'paywall_dismissed'
    /* Leaderboard */
    | 'leaderboard_view'
    | 'leaderboard_tab_switch'
    /* Marketing attribution */
    | 'campaign_click'
    | 'utm_capture'
    /* SEO */
    | 'seo_impression'
    | 'search_query'
    /* Feature-specific */
    | 'guide_open'
    | 'subject_hub_open'
    | 'comparison_open'
    | 'flashcard_review'
    | 'flashcard_flip'
    | 'flashcard_difficulty';

/** Loose shape — anything serialisable to GA4 / PostHog / Clarity */
export type EventParams = Record<
    string,
    string | number | boolean | null | undefined
>;

/* ----------------------------------------------------------------------- */
/* Vendor helpers                                                           */
/* ----------------------------------------------------------------------- */

function isBrowser(): boolean {
    return typeof window !== 'undefined';
}

function safeGtag(event: string, params?: EventParams): void {
    if (!isBrowser() || typeof window.gtag !== 'function') return;
    try {
        window.gtag('event', event, params ?? {});
    } catch {
        /* swallow — analytics must never break the page */
    }
}

function safeClarity(event: string, params?: EventParams): void {
    if (!isBrowser() || !window.clarity) return;
    try {
        // Clarity accepts "event" command — see https://learn.microsoft.com/en-us/clarity/
        window.clarity('event', event);
        if (params) {
            // Tag clarity with up to 3 lightweight tags for dashboard filtering
            Object.entries(params)
                .slice(0, 3)
                .forEach(([k, v]) => {
                    if (v != null) window.clarity?.('set', k, String(v));
                });
        }
    } catch {
        /* ignore */
    }
}

function safePosthog(event: string, params?: EventParams): void {
    if (!isBrowser() || !window.posthog) return;
    try {
        window.posthog.capture(event, params as Record<string, unknown>);
    } catch {
        /* ignore */
    }
}

function safeDdAction(name: string, params?: EventParams): void {
    if (!isBrowser() || !window.DD_RUM) return;
    try {
        window.DD_RUM.addUserAction(name, params as Record<string, unknown>);
    } catch {
        /* ignore */
    }
}

/** Fan out to every enabled vendor. Internal — do not call directly. */
function dispatch(event: AnalyticsEvent, params?: EventParams): void {
    safeGtag(event, params);
    safeClarity(event, params);
    safePosthog(event, params);
    safeDdAction(event, params);
}

/* ----------------------------------------------------------------------- */
/* Identity                                                                 */
/* ----------------------------------------------------------------------- */

let lastIdentifiedId: string | null = null;

export const identity = {
    /** Call after login / on profile hydrate. Idempotent across vendors. */
    set(user: User | null, traits?: EventParams): void {
        if (!isBrowser()) return;
        if (!user) {
            identity.clear();
            return;
        }
        const id = String(user.id);
        const base: EventParams = {
            user_id: id,
            username: user.username,
            email: user.email,
            role: user.role,
            target_exam: user.target_exam,
            is_subscribed: !!user.is_subscribed,
            is_admin: !!user.is_admin,
        };
        const merged: EventParams = { ...base, ...(traits ?? {}) };

        safeGtag('set', { user_id: id });
        // Set scalar user properties (GA4 user_properties bag requires a
        // nested object — we cast to gtag's loose type to avoid clashing
        // with our strict EventParams interface).
        try {
            const win = window as unknown as {
                gtag?: (cmd: string, ...args: unknown[]) => void;
            };
            win.gtag?.('set', 'user_properties', merged as unknown as Record<string, unknown>);
        } catch {
            /* ignore */
        }
        try {
            window.posthog?.identify(id, merged as Record<string, unknown>);
        } catch {
            /* ignore */
        }
        try {
            window.DD_RUM?.setUser({ id, ...merged });
        } catch {
            /* ignore */
        }
        lastIdentifiedId = id;
    },

    clear(): void {
        if (!isBrowser()) return;
        try {
            window.posthog?.reset();
        } catch {
            /* ignore */
        }
        try {
            window.DD_RUM?.clearUser();
        } catch {
            /* ignore */
        }
        lastIdentifiedId = null;
    },

    /** Returns the id used for the current identify call (for funnels). */
    currentId(): string | null {
        return lastIdentifiedId;
    },
};

/* ----------------------------------------------------------------------- */
/* UTM / campaign attribution                                               */
/* ----------------------------------------------------------------------- */

const UTM_KEYS = [
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'utm_term',
    'utm_content',
] as const;

const ATTRIBUTION_STORAGE_KEY = 'crackcms_attribution_v1';
const ATTRIBUTION_MAX_AGE_MS = 1000 * 60 * 60 * 24 * 30; // 30 days

interface Attribution {
    source: string;
    medium: string;
    campaign: string;
    term: string;
    content: string;
    landing_path: string;
    referrer: string;
    captured_at: string;
}

function emptyAttribution(): Attribution {
    return {
        source: 'direct',
        medium: 'none',
        campaign: '(not set)',
        term: '(not set)',
        content: '(not set)',
        landing_path: '',
        referrer: '',
        captured_at: new Date().toISOString(),
    };
}

/**
 * Captures the UTM params present in the URL on the *first* visit (or last
 * paid click) and persists them to localStorage. Subsequent visits attach
 * the same attribution to every event — so revenue funnels know which
 * campaign actually drove the sale.
 */
export const attribution = {
    capture(): Attribution | null {
        if (!isBrowser()) return null;
        const url = new URL(window.location.href);
        const params = url.searchParams;
        const hasUtm = UTM_KEYS.some((k) => params.has(k));
        const existing = attribution.read();

        // Always update landing_path on first hit
        if (!existing || hasUtm) {
            const next: Attribution = existing ?? emptyAttribution();
            UTM_KEYS.forEach((k) => {
                const v = params.get(k);
                if (v) {
                    next[k.replace('utm_', '') as keyof Attribution] = v as never;
                }
            });
            if (!existing) {
                next.landing_path = window.location.pathname;
                next.referrer = document.referrer || '(direct)';
            }
            next.captured_at = new Date().toISOString();
            try {
                localStorage.setItem(
                    ATTRIBUTION_STORAGE_KEY,
                    JSON.stringify(next),
                );
            } catch {
                /* ignore quota / private mode */
            }
            // Surface as an event so dashboards can see fresh captures
            dispatch('utm_capture', {
                source: next.source,
                medium: next.medium,
                campaign: next.campaign,
                term: next.term,
                content: next.content,
                referrer: next.referrer,
            });
            return next;
        }
        return existing;
    },

    read(): Attribution | null {
        if (!isBrowser()) return null;
        try {
            const raw = localStorage.getItem(ATTRIBUTION_STORAGE_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw) as Attribution;
            if (
                Date.now() - Date.parse(parsed.captured_at) >
                ATTRIBUTION_MAX_AGE_MS
            ) {
                localStorage.removeItem(ATTRIBUTION_STORAGE_KEY);
                return null;
            }
            return parsed;
        } catch {
            return null;
        }
    },

    /** Convenience for attaching to a single event without reading the rest. */
    attach<T extends EventParams>(params: T = {} as T): T & EventParams {
        const a = attribution.read();
        if (!a) return params as T & EventParams;
        return {
            ...params,
            utm_source: a.source,
            utm_medium: a.medium,
            utm_campaign: a.campaign,
            utm_term: a.term,
            utm_content: a.content,
        };
    },

    clear(): void {
        if (!isBrowser()) return;
        localStorage.removeItem(ATTRIBUTION_STORAGE_KEY);
    },
};

/* ----------------------------------------------------------------------- */
/* Session / device                                                         */
/* ----------------------------------------------------------------------- */

let sessionStartMarked = false;
let engagementTimer: ReturnType<typeof setInterval> | null = null;

function deviceContext(): EventParams {
    if (!isBrowser()) return {};
    const ua = navigator.userAgent;
    const lang = navigator.language || 'en';
    const conn = (navigator as Navigator & { connection?: { effectiveType?: string } }).connection;
    const e_type = conn?.effectiveType ?? '';
    return {
        device_type: /Mobi|Android/i.test(ua) ? 'mobile' : 'desktop',
        browser: browserFromUa(ua),
        os: osFromUa(ua),
        language: lang,
        connection_type: e_type,
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
    };
}

function browserFromUa(ua: string): string {
    if (/Edg\//.test(ua)) return 'Edge';
    if (/OPR\//.test(ua) || /Opera/.test(ua)) return 'Opera';
    if (/Chrome\//.test(ua) && !/Chromium/.test(ua)) return 'Chrome';
    if (/Safari\//.test(ua) && /Version\//.test(ua)) return 'Safari';
    if (/Firefox\//.test(ua)) return 'Firefox';
    return 'Other';
}

function osFromUa(ua: string): string {
    if (/Windows NT/.test(ua)) return 'Windows';
    if (/Mac OS X/.test(ua)) return 'macOS';
    if (/Android/.test(ua)) return 'Android';
    if (/iPhone|iPad|iPod/.test(ua)) return 'iOS';
    if (/Linux/.test(ua)) return 'Linux';
    return 'Other';
}

let visitedBefore = false;
if (isBrowser()) {
    try {
        visitedBefore = !!localStorage.getItem('crackcms_return_visit');
        localStorage.setItem('crackcms_return_visit', '1');
    } catch {
        /* ignore */
    }
}

export const session = {
    start(): void {
        if (sessionStartMarked) return;
        sessionStartMarked = true;
        const ctx: EventParams = {
            ...deviceContext(),
            return_visit: visitedBefore,
        };
        dispatch('session_start', ctx);
        if (visitedBefore) dispatch('return_visit', ctx);

        // Heartbeat engagement every 15s
        let lastTick = Date.now();
        if (engagementTimer) clearInterval(engagementTimer);
        engagementTimer = setInterval(() => {
            const now = Date.now();
            const delta = (now - lastTick) / 1000;
            lastTick = now;
            dispatch('engagement_time', { seconds: Math.round(delta) });
        }, 15000);
    },

    stop(): void {
        if (engagementTimer) {
            clearInterval(engagementTimer);
            engagementTimer = null;
        }
    },
};

/* ----------------------------------------------------------------------- */
/* Page tracking (called from TrafficAnalytics)                              */
/* ----------------------------------------------------------------------- */

let lastPagePath: string | null = null;

/**
 * Lightweight context attached to every backend-relayed event. Built
 * cheaply from the browser globals — no DOM walks.
 */
function buildServerContext(): EventParams {
    if (!isBrowser()) return {};
    const ua = navigator.userAgent;
    const ctx: EventParams = {
        visitor_id: getVisitorId(),
        session_id: getSessionId(),
        device_type: /Mobi|Android/i.test(ua) ? 'mobile' : 'desktop',
        browser: browserFromUa(ua),
        os: osFromUa(ua),
        language: navigator.language || 'en',
        referrer: document.referrer || '',
        path: window.location.pathname,
    };
    return ctx;
}

function getVisitorId(): string {
    if (!isBrowser()) return '';
    try {
        let id = localStorage.getItem('crackcms_visitor_id');
        if (!id) {
            id = (typeof crypto !== 'undefined' && 'randomUUID' in crypto
                ? crypto.randomUUID()
                : Math.random().toString(36).slice(2) + Date.now().toString(36));
            localStorage.setItem('crackcms_visitor_id', id);
        }
        return id;
    } catch {
        return '';
    }
}

function getSessionId(): string {
    if (!isBrowser()) return '';
    try {
        let id = sessionStorage.getItem('crackcms_session_id');
        if (!id) {
            id = (typeof crypto !== 'undefined' && 'randomUUID' in crypto
                ? crypto.randomUUID()
                : Math.random().toString(36).slice(2));
            sessionStorage.setItem('crackcms_session_id', id);
        }
        return id;
    } catch {
        return '';
    }
}

/**
 * Debounced relay — fire-and-forget to our backend, max 1 call per 50ms.
 * Listens only to high-value events so we don't flood the API. Pageview
 * + scroll + scroll-related fires are excluded — only the conversion
 * funnel + content events are mirrored to our backend.
 */
const RELAYED_EVENTS = new Set<AnalyticsEvent>([
    'sign_up',
    'login',
    'subscription_intent',
    'checkout_start',
    'payment_success',
    'payment_failure',
    'coupon_applied',
    'question_solve',
    'ai_tutor_message',
    'blog_view',
    'blog_read_complete',
    'leaderboard_view',
    'leaderboard_tab_switch',
    'campaign_click',
    'site_search',
]);

let pendingRelay: { event: AnalyticsEvent; params?: EventParams } | null = null;
let pendingTimer: ReturnType<typeof setTimeout> | null = null;

function maybeRelay(event: AnalyticsEvent, params?: EventParams): void {
    if (!isBrowser()) return;
    if (!RELAYED_EVENTS.has(event)) return;
    pendingRelay = { event, params };
    if (pendingTimer) return;
    pendingTimer = setTimeout(() => {
        const next = pendingRelay;
        pendingRelay = null;
        pendingTimer = null;
        if (!next) return;
        void analytics.relay(next.event, next.params);
    }, 50);
}

export function trackPageView(path: string, params?: EventParams): void {
    if (!isBrowser()) return;
    if (lastPagePath === path) return; // dedupe
    lastPagePath = path;
    const ctx: EventParams = {
        page_path: path,
        page_location: window.location.origin + path,
        page_title: document.title,
        page_referrer: document.referrer,
        ...deviceContext(),
        ...(params ?? {}),
    };
    dispatch('page_view', ctx);
}

/* ----------------------------------------------------------------------- */
/* Engagement (scroll depth + time on page)                                 */
/* ----------------------------------------------------------------------- */

let scrollMarked = new Set<number>();
let scrollTimer: ReturnType<typeof setTimeout> | null = null;

function bucketDepth(percent: number): number {
    if (percent >= 100) return 100;
    if (percent >= 75) return 75;
    if (percent >= 50) return 50;
    if (percent >= 25) return 25;
    return 0;
}

export function trackScrollDepth(force?: boolean): void {
    if (!isBrowser()) return;
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
        const scrollTop = window.scrollY;
        const docHeight =
            document.documentElement.scrollHeight - window.innerHeight;
        const percent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
        const bucket = bucketDepth(percent);
        if (!scrollMarked.has(bucket) || force) {
            scrollMarked.add(bucket);
            dispatch('scroll_depth', { percent_bucket: bucket, exact_percent: Math.round(percent) });
        }
    }, 150);
}

export function resetScrollTracking(): void {
    scrollMarked = new Set();
}

/* ----------------------------------------------------------------------- */
/* Paywall events (freemium conversion layer — 2026-08-02)                   */
/* ----------------------------------------------------------------------- */

/**
 * User saw the global UpgradeModal for a given feature. Fired on every
 * modal open. Used by the funnel dashboard to measure impressions.
 */
export function paywallView(feature: string, params?: EventParams): void {
    dispatch('paywall_view', { feature, ...(params ?? {}) });
}

/**
 * User clicked the "Start Now" CTA inside the modal. Strongest intent
 * signal — drops them onto /subscription?
 */
export function upgradeClick(feature: string, params?: EventParams): void {
    dispatch('upgrade_click', { feature, ...(params ?? {}) });
}

/**
 * User dismissed the modal without clicking the CTA (close button,
 * overlay click, or "Maybe later"). Used to compute impression-to-click
 * conversion; high dismissal rate suggests copy or trigger is wrong.
 */
export function paywallDismissed(feature: string, params?: EventParams): void {
    dispatch('paywall_dismissed', { feature, ...(params ?? {}) });
}

/* ----------------------------------------------------------------------- */
/* Public API                                                               */
/* ----------------------------------------------------------------------- */

export const analytics = {
    /* Lifecycle */
    pageView: trackPageView,
    sessionStart: session.start,
    sessionStop: session.stop,
    scrollDepth: trackScrollDepth,
    resetScroll: resetScrollTracking,

    identify: identity.set,
    reset: identity.clear,
    attribution,

    /* Generic helper — surface any event with safe fan-out */
    event(event: AnalyticsEvent, params?: EventParams): void {
        dispatch(event, params);
        maybeRelay(event, params);
    },

    /**
     * Fire-and-forget relay to our own backend (`/api/analytics/events/`).
     * Lets us power the internal admin dashboard from the same events
     * GA4 / PostHog see — without giving up those vendors. Lazy-loaded
     * (don't import api.ts at module top level so SSR doesn't pull it in).
     *
     * Per fan-out is debounced to 1 event / 50ms so a busy page
     * (e.g. simulator) can't flood the backend.
     */
    async relay(event: AnalyticsEvent, params?: EventParams): Promise<void> {
        try {
            const { analyticsAPI } = await import('./api');
            await analyticsAPI.ingestEvent({
                event_name: event,
                ...(params ?? {}),
                ...buildServerContext(),
            });
        } catch {
            /* failures are silent — analytics must never break the page */
        }
    },

    /* Convenience wrappers — keep call sites short + grep-able */
    ctaClick(name: string, location: string, extra?: EventParams): void {
        dispatch('cta_click', { cta_name: name, cta_location: location, ...(extra ?? {}) });
    },
    outbound(url: string, label?: string): void {
        dispatch('outbound_click', { outbound_url: url, outbound_label: label ?? '' });
    },
    internalLink(to: string, surface: string, label?: string): void {
        dispatch('internal_link_click', {
            link_target: to,
            link_surface: surface,
            link_label: label ?? '',
        });
    },
    siteSearch(query: string, resultsCount?: number): void {
        dispatch('site_search', { search_term: query, results_count: resultsCount ?? 0 });
    },
    searchResultClick(query: string, resultId: string | number, position: number): void {
        dispatch('search_result_click', {
            search_term: query,
            result_id: String(resultId),
            result_position: position,
        });
    },
    error(message: string, source: string, fatal = false): void {
        dispatch('error', { error_message: message, error_source: source, fatal });
    },

    /* Auth */
    signUp(method: string, plan?: string): void {
        dispatch('sign_up', { method, plan: plan ?? '' });
    },
    login(method: string): void {
        dispatch('login', { method });
    },
    logout(): void {
        dispatch('logout', {});
    },
    registerIntent(surface: string): void {
        dispatch('register_intent', { surface });
    },

    /* Blog */
    blogView(slug: string, category: string, readingTime: number): void {
        dispatch('blog_view', { blog_slug: slug, blog_category: category, reading_time: readingTime });
    },
    blogScroll(slug: string, percent: number): void {
        dispatch('blog_scroll_depth', { blog_slug: slug, percent });
    },
    blogReadComplete(slug: string, dwellSeconds: number): void {
        dispatch('blog_read_complete', { blog_slug: slug, dwell_seconds: dwellSeconds });
    },
    blogShare(slug: string, network: string): void {
        dispatch('blog_share', { blog_slug: slug, network });
    },
    blogCopyLink(slug: string): void {
        dispatch('blog_copy_link', { blog_slug: slug });
    },
    blogComment(slug: string): void {
        dispatch('blog_comment', { blog_slug: slug });
    },
    blogNewsletter(slug: string): void {
        dispatch('blog_newsletter_signup', { blog_slug: slug });
    },
    blogCta(slug: string, cta: string, surface: string): void {
        dispatch('blog_cta_click', { blog_slug: slug, cta_name: cta, cta_surface: surface });
    },

    /* Question bank / practice */
    questionView(questionId: number, subject: string, topic?: string): void {
        dispatch('question_view', {
            question_id: questionId,
            subject,
            topic: topic ?? '',
        });
    },
    questionSolve(
        questionId: number,
        subject: string,
        topic: string | undefined,
        isCorrect: boolean,
        timeMs: number,
    ): void {
        dispatch('question_solve', {
            question_id: questionId,
            subject,
            topic: topic ?? '',
            is_correct: isCorrect,
            time_ms: timeMs,
        });
    },
    questionSkip(questionId: number, subject: string): void {
        dispatch('question_skip', { question_id: questionId, subject });
    },
    questionBookmark(questionId: number, action: 'add' | 'remove'): void {
        dispatch('question_bookmark', { question_id: questionId, action });
    },
    aiExplanationOpen(questionId: number, subject: string): void {
        dispatch('ai_explanation_open', { question_id: questionId, subject });
    },
    aiExplanationFeedback(questionId: number, vote: 'up' | 'down'): void {
        dispatch('ai_explanation_feedback', { question_id: questionId, vote });
    },

    /* AI Tutor */
    aiTutorOpen(mode: string): void {
        dispatch('ai_tutor_open', { mode });
    },
    aiTutorConversationStart(mode: string): void {
        dispatch('ai_tutor_conversation_start', { mode });
    },
    aiTutorMessage(mode: string, messageLength: number, hasAttachments: boolean): void {
        dispatch('ai_tutor_message', {
            mode,
            message_length: messageLength,
            has_attachments: hasAttachments,
        });
    },
    aiTutorFeedback(sessionId: string, vote: 'up' | 'down'): void {
        dispatch('ai_tutor_feedback', { session_id: sessionId, vote });
    },

    /* Tests */
    pyqYearOpen(examSlug: string, year: number, solved: number, total: number): void {
        dispatch('pyq_year_open', {
            exam_slug: examSlug,
            year,
            solved,
            total,
        });
    },
    mockTestStart(examSlug: string, year: number | null, mode: string): void {
        dispatch('mock_test_start', {
            exam_slug: examSlug,
            year: year ?? 'all',
            mode,
        });
    },
    mockTestComplete(
        examSlug: string,
        score: number,
        total: number,
        accuracy: number,
    ): void {
        dispatch('mock_test_complete', {
            exam_slug: examSlug,
            score,
            total,
            accuracy,
        });
    },
    mockTestAbandon(examSlug: string, answered: number, total: number): void {
        dispatch('mock_test_abandon', {
            exam_slug: examSlug,
            answered,
            total,
        });
    },

    /* Subscription / revenue */
    subscriptionIntent(plan: string, surface: string): void {
        dispatch('subscription_intent', { plan, surface });
    },
    checkoutStart(plan: string, amount: number): void {
        dispatch('checkout_start', { plan, amount });
    },
    paymentSuccess(plan: string, amount: number, coupon: string | null): void {
        dispatch('payment_success', { plan, amount, coupon: coupon ?? '' });
    },
    paymentFailure(plan: string, reason: string): void {
        dispatch('payment_failure', { plan, reason });
    },
    couponApplied(plan: string, code: string, discount: number): void {
        dispatch('coupon_applied', { plan, code, discount });
    },

    /* Leaderboard */
    leaderboardView(tab: string): void {
        dispatch('leaderboard_view', { tab });
    },
    leaderboardTabSwitch(from: string, to: string): void {
        dispatch('leaderboard_tab_switch', { from, to });
    },

    /* SEO */
    seoImpression(query: string, position: number, page: string): void {
        dispatch('seo_impression', { search_query: query, position, landing_page: page });
    },
    searchQuery(query: string, landingPage: string): void {
        dispatch('search_query', { search_query: query, landing_page: landingPage });
    },

    /* Marketing */
    campaignClick(campaign: string, source: string, medium: string): void {
        dispatch('campaign_click', { campaign, source, medium });
    },

    /* Generic high-level helpers retained from the original lib */
    guideOpen(slug: string, category: string): void {
        dispatch('guide_open', { guide_slug: slug, category });
    },
    subjectHubOpen(examSlug: string, subject: string): void {
        dispatch('subject_hub_open', { exam_slug: examSlug, subject });
    },
    comparisonOpen(slug: string): void {
        dispatch('comparison_open', { comparison_slug: slug });
    },
    flashcardReview(cardId: number, difficulty: 'easy' | 'medium' | 'hard'): void {
        dispatch('flashcard_review', { card_id: cardId, difficulty });
    },
    flashcardFlip(cardId: number): void {
        dispatch('flashcard_flip', { card_id: cardId });
    },
};

export default analytics;
