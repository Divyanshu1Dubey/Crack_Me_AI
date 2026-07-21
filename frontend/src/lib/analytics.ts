/**
 * analytics.ts — Centralised GA4 custom-event helpers.
 *
 * Events fired here feed the conversions and audiences you configure in
 * Google Analytics 4 (https://analytics.google.com). All helpers are
 * no-ops when window.gtag is unavailable (SSR / dev).
 *
 * Recommended GA4 conversions to mark in the GA4 admin console:
 *   - sign_up            (default — fires from /register)
 *   - subscription_purchase
 *   - pyq_year_open
 *   - mock_test_start
 *   - ai_explain_request
 *   - register_intent
 */

declare global {
    interface Window {
        gtag?: (...args: unknown[]) => void;
        dataLayer?: unknown[];
    }
}

type GtagEvent =
    | 'pyq_year_open'
    | 'mock_test_start'
    | 'ai_explain_request'
    | 'register_intent'
    | 'subscription_intent'
    | 'guide_open'
    | 'subject_hub_open'
    | 'comparison_open';

function safeGtag(event: GtagEvent, params: Record<string, string | number | boolean> = {}): void {
    if (typeof window === 'undefined') return;
    if (typeof window.gtag !== 'function') return;
    window.gtag('event', event, params);
}

export const analytics = {
    /** User clicked a year tile in the Question Bank Year Stats panel. */
    pyqYearOpen(examSlug: string, year: number, solved: number, count: number): void {
        safeGtag('pyq_year_open', { exam_slug: examSlug, year, solved, total: count });
    },

    /** User entered Exam Mode for a year (or hit the banner Exam Mode button). */
    mockTestStart(examSlug: string, year: number | null): void {
        safeGtag('mock_test_start', { exam_slug: examSlug, year: year ?? 'all' });
    },

    /** User clicked Generate AI Analysis on a question. */
    aiExplainRequest(examSlug: string, questionId: number, subject: string): void {
        safeGtag('ai_explain_request', { exam_slug: examSlug, question_id: questionId, subject });
    },

    /** User clicked "Create free account" CTA from a non-auth surface. */
    registerIntent(surface: string): void {
        safeGtag('register_intent', { surface });
    },

    /** User clicked "Subscribe" / "View Premium Plans". */
    subscriptionIntent(plan: string): void {
        safeGtag('subscription_intent', { plan });
    },

    /** User opened a long-form guide page. */
    guideOpen(slug: string, category: string): void {
        safeGtag('guide_open', { guide_slug: slug, category });
    },

    /** User opened a subject-hub page. */
    subjectHubOpen(examSlug: string, subject: string): void {
        safeGtag('subject_hub_open', { exam_slug: examSlug, subject });
    },

    /** User opened an exam comparison page. */
    comparisonOpen(slug: string): void {
        safeGtag('comparison_open', { comparison_slug: slug });
    },
};

export default analytics;