/**
 * plans.ts — the premium plans the backend actually sells.
 *
 * Mirrors backend/accounts/models.py PLAN_FEATURES and the price table in
 * accounts/views.py SubscribeOrderView (PURCHASABLE_PLANS = 1_month,
 * 3_months, 1_year, scholarship_1_month). The old Rs 199 lifetime "legacy"
 * pass is no longer sold and must not be advertised anywhere.
 *
 * Used by the /subscription cards, the landing-page pricing section and the
 * Course / Offer structured data, so a price change is made in one place
 * (plus the backend tables above). Keep this file free of imports so it can
 * be unit-tested directly with Node.
 */

export type PurchasablePlanId = '1_month' | '3_months' | '1_year';

export interface PremiumPlan {
    id: PurchasablePlanId;
    name: string;
    priceInr: number;
    /** Human period used in "₹129 / month". */
    period: string;
    durationDays: number;
    /** Only the yearly plan bypasses token metering (PLAN_FEATURES.unlimited_ai). */
    unlimitedAi: boolean;
    /**
     * AI credits added to the wallet once, when the plan is activated
     * (Subscription.activate_from_payment). null = unlimited AI instead.
     */
    aiCreditsAtPurchase: number | null;
}

export const PREMIUM_PLANS: PremiumPlan[] = [
    {
        id: '1_month',
        name: '1 Month Pass',
        priceInr: 129,
        period: 'month',
        durationDays: 30,
        unlimitedAi: false,
        aiCreditsAtPurchase: 100,
    },
    {
        id: '3_months',
        name: '3 Months Pass',
        priceInr: 449,
        period: '3 months',
        durationDays: 90,
        unlimitedAi: false,
        aiCreditsAtPurchase: 300,
    },
    {
        id: '1_year',
        name: '1 Year Unlimited',
        priceInr: 1999,
        period: 'year',
        durationDays: 365,
        unlimitedAi: true,
        aiCreditsAtPurchase: null,
    },
];

/**
 * Scholarship rate shown in copy. The real price is set per student by the
 * backend (user.scholarship_granted_price, default Rs 79) after a perfect
 * score on the scholarship test.
 */
export const SCHOLARSHIP_PRICE_INR = 79;

export const LOWEST_PLAN_PRICE_INR = Math.min(...PREMIUM_PLANS.map((p) => p.priceInr));
export const HIGHEST_PLAN_PRICE_INR = Math.max(...PREMIUM_PLANS.map((p) => p.priceInr));

/** Free daily AI token allowance every account gets (accounts token wallet). */
export const FREE_DAILY_AI_TOKENS = 10;

/** Free practice questions every new account gets before the paywall. */
export const FREE_PRACTICE_QUESTIONS = 20;

/** schema.org AggregateOffer describing the real paid plans (INR). */
export function premiumAggregateOffer() {
    return {
        '@type': 'AggregateOffer',
        priceCurrency: 'INR',
        lowPrice: String(LOWEST_PLAN_PRICE_INR),
        highPrice: String(HIGHEST_PLAN_PRICE_INR),
        offerCount: PREMIUM_PLANS.length,
        availability: 'https://schema.org/InStock',
    };
}
