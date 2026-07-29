'use client';

/**
 * SubscriptionAnalytics.tsx — Tracks pricing-page intent + checkout funnel.
 *
 * Drop inside `/subscription`. Fires `subscription_intent` when the user
 * clicks any plan CTA; `checkout_start` / `payment_success` /
 * `payment_failure` should be fired from the calling component using
 * the helpers exported below.
 */

import { useEffect } from 'react';
import { analytics } from '@/lib/analytics';

export function trackPlanIntent(plan: string, surface: string): void {
    analytics.subscriptionIntent(plan, surface);
}

export function trackCheckoutStart(plan: string, amount: number): void {
    analytics.checkoutStart(plan, amount);
}

export function trackPaymentSuccess(plan: string, amount: number, coupon: string | null): void {
    analytics.paymentSuccess(plan, amount, coupon);
}

export function trackPaymentFailure(plan: string, reason: string): void {
    analytics.paymentFailure(plan, reason);
}

export function trackCouponApplied(plan: string, code: string, discount: number): void {
    analytics.couponApplied(plan, code, discount);
}

export default function SubscriptionAnalytics() {
    useEffect(() => {
        // Surface for delegating data-subscription-cta clicks
        const handler = (e: MouseEvent) => {
            const t = e.target as HTMLElement | null;
            if (!t) return;
            const cta = t.closest<HTMLElement>('[data-subscription-cta]');
            if (cta) {
                const plan = cta.getAttribute('data-subscription-plan') ?? 'unknown';
                const surface = cta.getAttribute('data-subscription-surface') ?? 'pricing';
                analytics.subscriptionIntent(plan, surface);
            }
        };
        document.addEventListener('click', handler);
        return () => document.removeEventListener('click', handler);
    }, []);
    return null;
}